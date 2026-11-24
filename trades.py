"""Trading window: offers between owners, checked and applied safely.

Flow: owner A offers players (and/or cash) to owner B for B's players (and/or
cash). B accepts, declines or counters. On accept the trade is checked again,
squads are changed through squads.record_change (so earlier points stay with
the old owner), and every other open offer that involves the moved players is
cancelled. The admin can reverse a trade within the reversal window.
"""
import copy
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

import db
import market
import squads
from models import TradeItem, TradeOffer
from storage import load_match_history, load_teams

ACTIVE = "open"


class TradeError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc)


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


# ── Squads and purses ────────────────────────────────────────────────────────

def purse(team: dict) -> int | None:
    """Purse left in lakhs = budget - sum of player prices (None if no budget)."""
    if team.get("budget") is None:
        return None
    return int(round(team["budget"] - sum(p.get("price", 0) or 0 for p in team.get("players", []))))


def _player(team: dict, name: str) -> dict | None:
    return next((p for p in team.get("players", []) if p.get("name") == name), None)


def match_lock(t) -> str | None:
    """Reason trades are blocked right now (a match is on or not yet scored)."""
    if not market.load(t)["rules"].get("block_during_matches"):
        return None
    try:
        import match_schedule
        sched = match_schedule.load(t).get("matches", {})
    except Exception:
        return None
    done = {m["match_id"] for m in load_match_history(t)}
    now_ms = _now().timestamp() * 1000
    for mid, e in sched.items():
        start = e.get("start_ms") or 0
        if start and start <= now_ms < start + 12 * 3600 * 1000 \
                and int(mid) not in done and not e.get("done"):
            return (f"{e.get('title') or 'A match'} is on or waiting to be scored. "
                    "Trades open again once it's scored.")
    return None


def _apply(teams: dict, a: str, b: str, give: list, get: list, cash: int) -> tuple[dict, list]:
    """Return (new teams, notes). give: players a -> b; get: players b -> a;
    cash > 0 paid by a to b. Raises TradeError on any rule problem."""
    new = copy.deepcopy(teams)
    if a not in new or b not in new:
        raise TradeError("One of these teams doesn't exist in this league.")
    if a == b:
        raise TradeError("Pick another team to trade with.")
    if not give and not get:
        raise TradeError("Add at least one player to the trade.")
    if len(set(give)) != len(give) or len(set(get)) != len(get):
        raise TradeError("A player is listed twice.")
    for name in give:
        if not _player(new[a], name):
            raise TradeError(f"{name} is no longer in {a}'s squad.")
    for name in get:
        if not _player(new[b], name):
            raise TradeError(f"{name} is no longer in {b}'s squad.")

    moving_ab = [_player(new[a], n) for n in give]
    moving_ba = [_player(new[b], n) for n in get]
    new[a]["players"] = [p for p in new[a]["players"] if p["name"] not in give] + moving_ba
    new[b]["players"] = [p for p in new[b]["players"] if p["name"] not in get] + moving_ab

    if cash:
        if new[a].get("budget") is None or new[b].get("budget") is None:
            raise TradeError("This league has no purses, so trades can't include money.")
        new[a]["budget"] = new[a]["budget"] - cash
        new[b]["budget"] = new[b]["budget"] + cash
    for owner in (a, b):
        left = purse(new[owner])
        if left is not None and left < 0:
            raise TradeError(f"{owner} would be {market.crores(-left)} over their purse.")

    notes = []
    for owner in (a, b):
        team = new[owner]
        names = {p["name"] for p in team["players"]}
        by_price = sorted(team["players"], key=lambda p: -(p.get("price") or 0))
        if team.get("captain") and team["captain"] not in names:
            pick = next((p["name"] for p in by_price if p["name"] != team.get("vice_captain")), None)
            notes.append(f"{owner}'s captain {team['captain']} moves; {pick or 'nobody'} is captain until changed.")
            team["captain"] = pick
        if team.get("vice_captain") and team["vice_captain"] not in names:
            pick = next((p["name"] for p in by_price if p["name"] != team.get("captain")), None)
            notes.append(f"{owner}'s vice-captain {team['vice_captain']} moves; {pick or 'nobody'} is vice-captain until changed.")
            team["vice_captain"] = pick
    return new, notes


def preview(t, a: str, b: str, give: list, get: list, cash: int) -> dict:
    """Before/after for both teams, or an error message."""
    teams = load_teams(t).get("teams", {})
    try:
        new, notes = _apply(teams, a, b, give, get, cash)
    except TradeError as exc:
        return {"ok": False, "error": str(exc)}
    side = lambda o: {"owner": o, "purse_before": purse(teams[o]), "purse_after": purse(new[o]),
                      "count_before": len(teams[o]["players"]), "count_after": len(new[o]["players"])}
    return {"ok": True, "a": side(a), "b": side(b), "notes": notes}


# ── Offers ───────────────────────────────────────────────────────────────────

def _expire_old(s, tid: str) -> None:
    for o in s.scalars(select(TradeOffer).where(TradeOffer.tournament_id == tid,
                                                TradeOffer.status == ACTIVE)):
        if _aware(o.expires_at) <= _now():
            o.status, o.status_note, o.responded_at = "expired", "No answer in time.", _now()


def _check_open(t) -> None:
    m = market.load(t)
    if m["mode"] != "trading" or m["stage"] != "live":
        raise TradeError("The trading window isn't open right now.")
    lock = match_lock(t)
    if lock:
        raise TradeError(lock)


def make_offer(t, from_owner: str, to_owner: str, give: list, get: list, cash: int,
               message: str = "", by: str = "", parent_id: int | None = None) -> int:
    _check_open(t)
    _apply(load_teams(t).get("teams", {}), from_owner, to_owner, give, get, cash)  # validate
    hours = int(market.load(t)["rules"]["offer_expiry_hours"])
    with db.session() as s:
        o = TradeOffer(tournament_id=t.id, from_owner=from_owner, to_owner=to_owner, cash=cash,
                       message=(message or "").strip()[:200] or None, created_by=by,
                       expires_at=_now() + timedelta(hours=hours), parent_id=parent_id)
        o.items = [TradeItem(player_name=n, giver=from_owner) for n in give] + \
                  [TradeItem(player_name=n, giver=to_owner) for n in get]
        s.add(o)
        s.flush()
        return o.id


def _load(s, t, offer_id: int) -> TradeOffer:
    o = s.get(TradeOffer, offer_id)
    if o is None or o.tournament_id != t.id:
        raise TradeError("Offer not found.")
    _expire_old(s, t.id)
    return o


def _sides(o: TradeOffer) -> tuple[list, list]:
    give = [i.player_name for i in o.items if i.giver == o.from_owner]
    get = [i.player_name for i in o.items if i.giver == o.to_owner]
    return give, get


def accept(t, offer_id: int, by_owner: str) -> dict:
    """The receiving team accepts. Applies the trade. Returns summary."""
    _check_open(t)
    with db.session() as s:
        o = _load(s, t, offer_id)
        if o.to_owner != by_owner:
            raise TradeError("Only the team receiving the offer can accept it.")
        if o.status != ACTIVE:
            raise TradeError(f"This offer is {o.status} and can't be accepted.")
        give, get = _sides(o)
        teams = load_teams(t).get("teams", {})
        new, notes = _apply(teams, o.from_owner, o.to_owner, give, get, o.cash)
        version = squads.record_change(
            t, new, f"Trade #{o.id}: {o.from_owner} <-> {o.to_owner}")
        o.status, o.responded_at, o.squad_version = "accepted", _now(), version
        o.status_note = " ".join(notes) or None

        moved = set(give) | set(get)
        cancelled = []
        for other in s.scalars(select(TradeOffer).where(
                TradeOffer.tournament_id == t.id, TradeOffer.status == ACTIVE,
                TradeOffer.id != o.id)):
            if moved & {i.player_name for i in other.items}:
                other.status, other.responded_at = "cancelled", _now()
                other.status_note = f"A player in this offer was traded in trade #{o.id}."
                cancelled.append(other.id)
        return {"offer_id": o.id, "version": version, "notes": notes, "cancelled": cancelled}


def respond(t, offer_id: int, action: str, by_owner: str) -> None:
    """decline (receiver) or withdraw (sender)."""
    with db.session() as s:
        o = _load(s, t, offer_id)
        if o.status != ACTIVE:
            raise TradeError(f"This offer is already {o.status}.")
        if action == "decline" and o.to_owner == by_owner:
            o.status = "declined"
        elif action == "withdraw" and o.from_owner == by_owner:
            o.status = "withdrawn"
        else:
            raise TradeError("You can't do that with this offer.")
        o.responded_at = _now()


def counter(t, offer_id: int, by_owner: str, give: list, get: list, cash: int, message: str = "",
            by: str = "") -> int:
    """Receiver sends back changed terms: a new offer from them, the old one marked countered.
    give/get are from the counter-er's point of view."""
    with db.session() as s:
        o = _load(s, t, offer_id)
        if o.status != ACTIVE or o.to_owner != by_owner:
            raise TradeError("You can only counter an open offer made to you.")
        other = o.from_owner
    new_id = make_offer(t, by_owner, other, give, get, cash, message, by=by, parent_id=offer_id)
    with db.session() as s:
        o = s.get(TradeOffer, offer_id)
        o.status, o.responded_at, o.status_note = "countered", _now(), f"Counter-offer #{new_id}."
    return new_id


def reverse(t, offer_id: int, note: str = "") -> None:
    """Admin: undo an accepted trade (from now on; points already scored stay)."""
    hours = int(market.load(t)["rules"]["reversal_hours"])
    with db.session() as s:
        o = _load(s, t, offer_id)
        if o.status != "accepted":
            raise TradeError("Only accepted trades can be reversed.")
        if _now() - _aware(o.responded_at) > timedelta(hours=hours):
            raise TradeError(f"Trades can only be reversed within {hours} hours.")
        give, get = _sides(o)
        teams = load_teams(t).get("teams", {})
        try:
            new, _notes = _apply(teams, o.to_owner, o.from_owner, give, get, o.cash)
        except TradeError as exc:
            raise TradeError(f"Can't reverse: {exc} (a player may have been traded again).")
        # put captains back if they were moved by this trade
        prev = next((v for v in squads.load_history(t) if v["version"] == (o.squad_version or 0) - 1), None)
        if prev:
            for owner in (o.from_owner, o.to_owner):
                names = {p["name"] for p in new[owner]["players"]}
                for role in ("captain", "vice_captain"):
                    if prev["teams"].get(owner, {}).get(role) in names:
                        new[owner][role] = prev["teams"][owner][role]
        squads.record_change(t, new, f"Reversal of trade #{o.id}")
        o.status, o.status_note = "reversed", (note or "Reversed by the admin.")[:200]


def set_captains(t, owner: str, captain: str, vice_captain: str, by: str) -> None:
    """Change a team's captain and vice-captain (recorded as a squad change)."""
    teams = copy.deepcopy(load_teams(t).get("teams", {}))
    team = teams.get(owner)
    if team is None:
        raise TradeError("No such team.")
    names = {p["name"] for p in team.get("players", [])}
    if captain not in names or vice_captain not in names:
        raise TradeError("Pick the captain and vice-captain from your own squad.")
    if captain == vice_captain:
        raise TradeError("Captain and vice-captain must be different players.")
    if team.get("captain") == captain and team.get("vice_captain") == vice_captain:
        return
    team["captain"], team["vice_captain"] = captain, vice_captain
    squads.record_change(t, teams, f"{owner}: captain {captain}, vice-captain {vice_captain} ({by})")


def top_up_purses(t, lakhs: int) -> int:
    """Admin: add the same amount to every team's budget (e.g. for a new season).
    Recorded as a squad change. Returns how many teams were topped up."""
    if lakhs <= 0:
        raise TradeError("Enter an amount above zero.")
    teams = copy.deepcopy(load_teams(t).get("teams", {}))
    n = 0
    for team in teams.values():
        if team.get("budget") is not None:
            team["budget"] = team["budget"] + lakhs
            n += 1
    if not n:
        raise TradeError("These teams have no purses to top up.")
    squads.record_change(t, teams, f"Purse top-up: +{market.crores(lakhs)} for every team")
    return n


def offers(t, owner: str | None = None, statuses: tuple | None = None) -> list:
    """Offers as plain dicts, newest first. owner: only offers involving that team."""
    with db.session() as s:
        _expire_old(s, t.id)
        q = select(TradeOffer).where(TradeOffer.tournament_id == t.id)
        if owner:
            q = q.where(or_(TradeOffer.from_owner == owner, TradeOffer.to_owner == owner))
        if statuses:
            q = q.where(TradeOffer.status.in_(statuses))
        out = []
        hours = int(market.load(t)["rules"]["reversal_hours"])
        for o in s.scalars(q.order_by(TradeOffer.created_at.desc(), TradeOffer.id.desc())):
            give, get = _sides(o)
            out.append({
                "id": o.id, "from": o.from_owner, "to": o.to_owner, "give": give, "take": get,
                "cash": o.cash, "message": o.message, "status": o.status, "note": o.status_note,
                "created_at": _aware(o.created_at), "expires_at": _aware(o.expires_at),
                "responded_at": _aware(o.responded_at), "parent_id": o.parent_id,
                "reversible": o.status == "accepted" and o.responded_at is not None
                              and _now() - _aware(o.responded_at) <= timedelta(hours=hours),
            })
        return out


def pending_count(t, owner: str) -> int:
    """Open offers waiting for this team's answer."""
    return sum(1 for o in offers(t, owner, ("open",)) if o["to"] == owner)

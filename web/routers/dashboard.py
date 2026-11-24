"""Dashboard routes - main views for scores and analytics."""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from config import LeagueConfig
import market as market_mod
import profiles
import team_names
import tournaments
from web.auth import require_auth, User
from web.services import (
    get_leaderboard_data,
    get_match_history_data,
    get_master_scoresheet_data,
    get_match_detail_data,
    get_dashboard_stats,
    get_season_form,
    get_team_page_data,
)
from web.analytics import get_analytics_summary


router = APIRouter()

templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)
from web.template_globals import register as _register_globals
_register_globals(templates)


def _get_league(request: Request) -> LeagueConfig:
    """Pick the tournament from the URL prefix, e.g. /wpl/2027/... -> wpl-2027."""
    t = tournaments.from_path(request.url.path)
    if t is None:
        raise HTTPException(status_code=404, detail="Unknown tournament")
    return t


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, user: User = Depends(require_auth)):
    league = _get_league(request)
    leaderboard = get_leaderboard_data(league)
    stats = get_dashboard_stats(league)
    form = get_season_form(league)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "leaderboard": leaderboard,
            "stats": stats,
            "form": form,
            "people": profiles.for_teams(league.id),
            "page": "home",
            "league": league,
        }
    )


@router.get("/history", response_class=HTMLResponse)
async def match_history(request: Request, user: User = Depends(require_auth)):
    league = _get_league(request)
    history = get_match_history_data(league)
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "user": user,
            "history": history,
            "page": "history",
            "league": league,
        }
    )


@router.get("/master", response_class=HTMLResponse)
async def master_scoresheet(request: Request, user: User = Depends(require_auth)):
    league = _get_league(request)
    master = get_master_scoresheet_data(league)
    return templates.TemplateResponse(
        request=request,
        name="master.html",
        context={
            "user": user,
            "master": master,
            "page": "master",
            "league": league,
        }
    )


@router.get("/match/{match_id}", response_class=HTMLResponse)
async def match_detail(
    request: Request,
    match_id: int,
    user: User = Depends(require_auth)
):
    league = _get_league(request)
    try:
        detail = get_match_detail_data(match_id, league)
        return templates.TemplateResponse(
            request=request,
            name="match_detail.html",
            context={
                "user": user,
                "detail": detail,
                "match_id": match_id,
                "page": "match",
                "league": league,
            }
        )
    except FileNotFoundError:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "user": user,
                "error": f"Match {match_id} not found or not yet processed",
                "status_code": 404,
            },
            status_code=404
        )


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, user: User = Depends(require_auth)):
    league = _get_league(request)
    analytics = get_analytics_summary(league)
    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "user": user,
            "analytics": analytics,
            "page": "analytics",
            "league": league,
        }
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, user: User = Depends(require_auth)):
    """Scoring admin: API budget, schedule, manual scorecard upload."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    import match_schedule
    from cricbuzz_api import usage_summary
    league = _get_league(request)
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "league": league,
            "page": "admin",
            "usage": usage_summary(),
            "sched": match_schedule.summary(league),
        },
    )


@router.get("/team/{owner}", response_class=HTMLResponse)
async def team_page(owner: str, request: Request, user: User = Depends(require_auth),
                    welcome: int = 0, renamed: int = 0, rename_error: str = ""):
    """One fantasy team: owner card, standing, squad, match by match."""
    league = _get_league(request)
    team = get_team_page_data(league, owner)
    if team is None:
        raise HTTPException(status_code=404, detail=f"No team called {owner} in {league.name}")
    person = profiles.for_teams(league.id).get(owner)
    return templates.TemplateResponse(
        request=request,
        name="team.html",
        context={
            "user": user, "league": league, "team": team, "person": person,
            "page": "team" if user.teams.get(league.id) == owner else "home",
            "is_me": user.is_owner and user.teams.get(league.id) == owner,
            "welcome": welcome, "renamed": renamed, "rename_error": rename_error[:200],
            "owner_can_rename": team_names.owner_can_rename(league.id, owner),
            "cvc": market_mod.cvc_open(league),
        },
    )


@router.post("/team/{owner}/name")
async def rename_team(owner: str, request: Request, user: User = Depends(require_auth)):
    """The team's owner (or the admin) sets its display name."""
    from urllib.parse import quote
    from storage import load_teams
    league = _get_league(request)
    owners = list(load_teams(league).get("teams", {}).keys())
    if owner not in owners:
        raise HTTPException(status_code=404, detail="No such team")
    if not (user.is_admin or (user.is_owner and user.teams.get(league.id) == owner)):
        raise HTTPException(status_code=403, detail="Only this team's owner can rename it")
    form = await request.form()
    base = f"{league.dashboard_prefix}/team/{quote(owner)}"
    try:
        if user.is_admin and form.get("allow_owner"):
            team_names.allow_owner_again(league.id, owner)
            return RedirectResponse(f"{base}?renamed=2", status_code=303)
        team_names.set_name(league.id, owner, str(form.get("name", "")), owners,
                            by="admin" if user.is_admin else f"user:{user.id}",
                            is_admin=user.is_admin)
    except ValueError as exc:
        return RedirectResponse(f"{base}?rename_error={quote(str(exc))}", status_code=303)
    return RedirectResponse(f"{base}?renamed=1", status_code=303)


# ── Market: trading window ───────────────────────────────────────────────────

def _market_redirect(league, msg: str = "", err: str = "", anchor: str = ""):
    from urllib.parse import quote
    q = f"?msg={quote(msg)}" if msg else (f"?err={quote(err)}" if err else "")
    return RedirectResponse(f"{league.dashboard_prefix}/market{q}{anchor}", status_code=303)


def _my_team(user: User, league) -> str | None:
    return user.teams.get(league.id) if user.is_owner else None


@router.get("/market", response_class=HTMLResponse)
async def market_page(request: Request, user: User = Depends(require_auth),
                      counter: int = 0, to: str = "", msg: str = "", err: str = ""):
    import market
    import trades
    from storage import load_teams
    league = _get_league(request)
    m = market.load(league)
    if m["stage"] == "off" and not user.is_admin:
        raise HTTPException(status_code=404, detail="The market isn't open for this league.")
    teams = load_teams(league).get("teams", {})
    mine = _my_team(user, league)
    squads_view = {
        o: {"players": sorted(tm.get("players", []), key=lambda p: -(p.get("price") or 0)),
            "purse": trades.purse(tm), "captain": tm.get("captain"), "vc": tm.get("vice_captain")}
        for o, tm in teams.items()}
    all_offers = trades.offers(league)
    prefill = None
    if counter:
        o = next((x for x in all_offers if x["id"] == counter and x["to"] == mine and x["status"] == "open"), None)
        if o:   # counter-er's view: they give what they were asked for, get what was offered
            prefill = {"to": o["from"], "give": o["take"], "take": o["give"],
                       "cash": -o["cash"], "counter_of": o["id"]}
    elif to and to in teams and to != mine:
        prefill = {"to": to, "give": [], "take": [], "cash": 0, "counter_of": 0}
    return templates.TemplateResponse(request=request, name="market.html", context={
        "user": user, "league": league, "page": "market", "m": m, "stages": market.STAGES,
        "stage_labels": market.STAGE_LABELS, "mine": mine, "squads": squads_view,
        "incoming": [o for o in all_offers if o["to"] == mine and o["status"] == "open"] if mine else [],
        "outgoing": [o for o in all_offers if o["from"] == mine and o["status"] == "open"] if mine else [],
        "my_past": [o for o in all_offers if mine in (o["from"], o["to"]) and o["status"] not in ("open", "accepted", "reversed")][:20] if mine else [],
        "log": [o for o in all_offers if o["status"] in ("accepted", "reversed")],
        "open_all": [o for o in all_offers if o["status"] == "open"] if user.is_admin else [],
        "lock": trades.match_lock(league), "prefill": prefill, "msg": msg[:300], "err": err[:300],
    })


def _parse_offer_form(form) -> tuple[list, list, int]:
    import market
    give = [str(x) for x in form.getlist("give")]
    get = [str(x) for x in form.getlist("get")]
    amount = market.to_lakhs(str(form.get("cash_amount", "")))
    cash = amount if form.get("cash_dir", "pay") == "pay" else -amount
    return give, get, cash


@router.post("/market/preview")
async def market_preview(request: Request, user: User = Depends(require_auth)):
    import market
    import trades
    league = _get_league(request)
    mine = _my_team(user, league)
    form = await request.form()
    if not mine:
        return JSONResponse({"ok": False, "error": "Only team owners can trade."})
    try:
        give, get, cash = _parse_offer_form(form)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc) or "Enter an amount like 20 or 2.5"})
    p = trades.preview(league, mine, str(form.get("to", "")), give, get, cash)
    if p.get("ok"):
        for side in ("a", "b"):
            for k in ("purse_before", "purse_after"):
                v = p[side][k]
                p[side][k + "_text"] = market.crores(v) if v is not None else "–"
    return JSONResponse(p)


@router.post("/market/offer")
async def market_offer(request: Request, user: User = Depends(require_auth)):
    import trades
    league = _get_league(request)
    mine = _my_team(user, league)
    if not mine:
        raise HTTPException(status_code=403, detail="Only team owners can trade.")
    form = await request.form()
    try:
        give, get, cash = _parse_offer_form(form)
        to = str(form.get("to", ""))
        counter_of = int(form.get("counter_of") or 0)
        if counter_of:
            oid = trades.counter(league, counter_of, mine, give, get, cash,
                                 str(form.get("message", "")), by=f"user:{user.id}")
        else:
            oid = trades.make_offer(league, mine, to, give, get, cash,
                                    str(form.get("message", "")), by=f"user:{user.id}")
    except ValueError as exc:
        return _market_redirect(league, err=str(exc) or "Check the amount.", anchor="#new-offer")
    return _market_redirect(league, msg=f"sent:{oid}")


@router.post("/market/offer/{offer_id}/{action}")
async def market_action(offer_id: int, action: str, request: Request,
                        user: User = Depends(require_auth)):
    import trades
    league = _get_league(request)
    try:
        if action == "reverse":
            if not user.is_admin:
                raise HTTPException(status_code=403)
            form = await request.form()
            trades.reverse(league, offer_id, str(form.get("note", "")))
            return _market_redirect(league, msg=f"Trade #{offer_id} reversed. Squads and purses are back as before; points already scored stay.")
        mine = _my_team(user, league)
        if not mine:
            raise HTTPException(status_code=403)
        if action == "accept":
            r = trades.accept(league, offer_id, mine)
            extra = f" {len(r['cancelled'])} other offer(s) with these players were cancelled." if r["cancelled"] else ""
            return _market_redirect(league, msg=f"Trade #{offer_id} done! Squads are updated from the next match.{extra} " + " ".join(r["notes"]))
        if action in ("decline", "withdraw"):
            trades.respond(league, offer_id, action, mine)
            return _market_redirect(league, msg=f"Offer #{offer_id} {action}n." if action == "withdraw" else f"Offer #{offer_id} declined.")
    except trades.TradeError as exc:
        return _market_redirect(league, err=str(exc))
    raise HTTPException(status_code=404)


@router.post("/market/settings")
async def market_settings(request: Request, user: User = Depends(require_auth)):
    import market
    if not user.is_admin:
        raise HTTPException(status_code=403)
    league = _get_league(request)
    form = await request.form()
    rules = {}
    for k in ("offer_expiry_hours", "reversal_hours"):
        try:
            rules[k] = max(1, min(24 * 30, int(form.get(k))))
        except (TypeError, ValueError):
            pass
    rules["block_during_matches"] = bool(form.get("block_during_matches"))
    market.update(league, cvc_locked=bool(form.get("cvc_locked")))
    if str(form.get("top_up", "")).strip():
        import trades
        try:
            amount = market.to_lakhs(str(form.get("top_up")))
            n = trades.top_up_purses(league, amount)
        except ValueError as exc:
            return _market_redirect(league, err=f"Top-up not done: {exc}")
        market.update(league, rules=rules)
        log = market.load(league)
        log.setdefault("top_ups", []).append({"lakhs": amount, "teams": n})
        market.save(league, log)
        return _market_redirect(league, msg=f"Added ₹{market.crores(amount)} to {n} purses. Other settings saved.")
    market.update(league, stage=str(form.get("stage")) if form.get("stage") else None,
                  opens_at=form.get("opens_at"), closes_at=form.get("closes_at"),
                  note=form.get("note"), rules=rules)
    return _market_redirect(league, msg="Market settings saved.")


@router.post("/team/{owner}/captains")
async def set_captains(owner: str, request: Request, user: User = Depends(require_auth)):
    """Owner picks captain and vice-captain before the tournament starts (admin any time)."""
    import trades
    from urllib.parse import quote
    league = _get_league(request)
    is_me = user.is_owner and user.teams.get(league.id) == owner
    if not (user.is_admin or is_me):
        raise HTTPException(status_code=403, detail="Only this team's owner can change captains")
    base = f"{league.dashboard_prefix}/team/{quote(owner)}"
    if not user.is_admin:
        ok, reason = market_mod.cvc_open(league)
        if not ok:
            return RedirectResponse(f"{base}?rename_error={quote(reason)}", status_code=303)
    form = await request.form()
    try:
        trades.set_captains(league, owner, str(form.get("captain", "")), str(form.get("vice_captain", "")),
                            by="admin" if user.is_admin else "owner")
    except trades.TradeError as exc:
        return RedirectResponse(f"{base}?rename_error={quote(str(exc))}", status_code=303)
    return RedirectResponse(f"{base}?renamed=3#squad-h", status_code=303)

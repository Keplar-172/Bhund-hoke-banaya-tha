"""Owner accounts: join links, claiming a team, consent, deletion.

Flow
  admin creates a join link for (tournament, owner) -> sends it on WhatsApp
  owner opens /join/<token> -> enters name + email (+ consent) -> logged in
  lost phone: admin creates a "log in again" link for that person
Only a SHA-256 of each token is stored, so a database copy can't be used to log in.
"""
import csv
import hashlib
import io
import re
import secrets

from sqlalchemy import select

import db
from models import Consent, Invite, Membership, User, utcnow

NOTICE_VERSION = "2026-11-24"   # bump when the privacy notice changes
PURPOSES = {
    "service_emails": "Match, auction and account emails",
    "news": "Occasional news about Gully XI",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ClaimError(ValueError):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# ── Invites ──────────────────────────────────────────────────────────────────

def create_invite(tournament_id: str, owner_name: str) -> str:
    """New join link for a team; older unused links for it stop working.
    If someone already owns the team, the link logs that person in again
    (for a new phone) instead of letting someone else claim it."""
    token = secrets.token_urlsafe(24)
    with db.session() as s:
        for old in s.scalars(select(Invite).where(
                Invite.tournament_id == tournament_id, Invite.owner_name == owner_name,
                Invite.used_at.is_(None), Invite.revoked.is_(False))):
            old.revoked = True
        m = s.scalar(select(Membership).where(
            Membership.tournament_id == tournament_id, Membership.owner_name == owner_name))
        s.add(Invite(token_hash=_hash(token), tournament_id=tournament_id,
                     owner_name=owner_name, for_user_id=m.user_id if m else None))
    return token


def revoke_invites(tournament_id: str, owner_name: str) -> None:
    with db.session() as s:
        for inv in s.scalars(select(Invite).where(
                Invite.tournament_id == tournament_id, Invite.owner_name == owner_name,
                Invite.used_at.is_(None))):
            inv.revoked = True


def lookup_invite(token: str) -> dict | None:
    """{'tournament_id','owner_name','state','relogin','claimed_by'} or None."""
    with db.session() as s:
        inv = s.scalar(select(Invite).where(Invite.token_hash == _hash(token or "")))
        if inv is None:
            return None
        m = s.scalar(select(Membership).where(
            Membership.tournament_id == inv.tournament_id,
            Membership.owner_name == inv.owner_name))
        state = "revoked" if inv.revoked else "used" if inv.used_at else "open"
        return {"tournament_id": inv.tournament_id, "owner_name": inv.owner_name,
                "state": state, "relogin": inv.for_user_id is not None,
                "claimed_by": m.user_id if m else None}


def use_relogin(token: str) -> int:
    """Consume a 'log in again' link. Returns the user id."""
    with db.session() as s:
        inv = s.scalar(select(Invite).where(Invite.token_hash == _hash(token)))
        if not inv or inv.revoked or inv.used_at or not inv.for_user_id:
            raise ClaimError("This link has expired. Ask the admin for a new one.")
        inv.used_at = utcnow()
        return inv.for_user_id


def claim(token: str, name: str, email: str, phone: str | None,
          service_emails: bool, news: bool, current_user_id: int | None = None) -> int:
    """Claim the team behind a join link. Returns the user id to log in."""
    name = (name or "").strip()[:80]
    email = normalize_email(email)
    phone = (phone or "").strip()[:32] or None
    with db.session() as s:
        inv = s.scalar(select(Invite).where(Invite.token_hash == _hash(token)))
        if not inv or inv.revoked:
            raise ClaimError("This link is no longer valid. Ask the admin for a new one.")
        if inv.used_at:
            raise ClaimError("This link has already been used. Ask the admin for a new one.")
        if s.scalar(select(Membership).where(Membership.tournament_id == inv.tournament_id,
                                             Membership.owner_name == inv.owner_name)):
            raise ClaimError("This team has already been claimed. If that's you on a new "
                             "phone, ask the admin for a log-in link.")

        if current_user_id:                       # already logged in: add this team
            user = s.get(User, current_user_id)
            if user is None:
                raise ClaimError("Please log in again.")
        else:
            if not name:
                raise ClaimError("Please enter your name.")
            if not _EMAIL.match(email):
                raise ClaimError("Please enter a valid email address.")
            if s.scalar(select(User).where(User.email == email)):
                raise ClaimError("This email already has a Gully XI account. Open this link "
                                 "on the phone where you're logged in, or ask the admin.")
            user = User(name=name, email=email, phone=phone)
            s.add(user)
            s.flush()
            _set_consents(s, user.id, {"service_emails": service_emails, "news": news})

        s.add(Membership(user_id=user.id, tournament_id=inv.tournament_id,
                         owner_name=inv.owner_name))
        inv.used_at = utcnow()
        return user.id


# ── Users ────────────────────────────────────────────────────────────────────

def _set_consents(s, user_id: int, choices: dict) -> None:
    current = _latest_consents(s, user_id)
    for purpose, granted in choices.items():
        if purpose in PURPOSES and current.get(purpose) != bool(granted):
            s.add(Consent(user_id=user_id, purpose=purpose, granted=bool(granted),
                          notice_version=NOTICE_VERSION))


def _latest_consents(s, user_id: int) -> dict:
    out = {}
    for c in s.scalars(select(Consent).where(Consent.user_id == user_id).order_by(Consent.at, Consent.id)):
        out[c.purpose] = c.granted
    return out


def get_profile(user_id: int) -> dict | None:
    with db.session() as s:
        u = s.get(User, user_id)
        if u is None:
            return None
        u.last_seen_at = utcnow()
        return {
            "id": u.id, "name": u.name, "email": u.email, "phone": u.phone,
            "created_at": u.created_at,
            "teams": [{"tournament_id": m.tournament_id, "owner_name": m.owner_name}
                      for m in u.memberships],
            "consents": _latest_consents(s, u.id),
            "consent_log": [{"purpose": c.purpose, "granted": c.granted, "at": c.at,
                             "notice_version": c.notice_version} for c in u.consents],
        }


def update_profile(user_id: int, name: str, phone: str | None, choices: dict) -> None:
    with db.session() as s:
        u = s.get(User, user_id)
        if u is None:
            raise ClaimError("Account not found.")
        if (name or "").strip():
            u.name = name.strip()[:80]
        u.phone = (phone or "").strip()[:32] or None
        _set_consents(s, user_id, choices)


def delete_user(user_id: int) -> None:
    """Delete the person, their consents and team claims. The teams and their
    points stay in the league; the admin can send a new join link."""
    import profiles
    profiles.delete_files_for(user_id)
    with db.session() as s:
        u = s.get(User, user_id)
        if u is not None:
            for inv in s.scalars(select(Invite).where(Invite.for_user_id == user_id)):
                s.delete(inv)
            s.delete(u)


def release_team(tournament_id: str, owner_name: str) -> None:
    """Admin: undo a claim (wrong person claimed). The account itself stays."""
    with db.session() as s:
        m = s.scalar(select(Membership).where(Membership.tournament_id == tournament_id,
                                              Membership.owner_name == owner_name))
        if m:
            s.delete(m)
    revoke_invites(tournament_id, owner_name)


# ── Admin views ──────────────────────────────────────────────────────────────

def team_status(tournament_id: str, owner_names: list) -> list:
    """One row per owner: who claimed it and whether a link is waiting."""
    with db.session() as s:
        claims = {m.owner_name: m for m in s.scalars(
            select(Membership).where(Membership.tournament_id == tournament_id))}
        pending = {i.owner_name for i in s.scalars(select(Invite).where(
            Invite.tournament_id == tournament_id, Invite.used_at.is_(None),
            Invite.revoked.is_(False)))}
        rows = []
        for owner in owner_names:
            m = claims.get(owner)
            rows.append({"owner": owner, "link_pending": owner in pending,
                         "user": {"id": m.user.id, "name": m.user.name, "email": m.user.email}
                         if m else None})
        return rows


def all_users() -> list:
    with db.session() as s:
        out = []
        for u in s.scalars(select(User).order_by(User.created_at)):
            c = _latest_consents(s, u.id)
            out.append({"id": u.id, "name": u.name, "email": u.email, "phone": u.phone,
                        "created_at": u.created_at, "last_seen_at": u.last_seen_at,
                        "teams": [f"{m.tournament_id}: {m.owner_name}" for m in u.memberships],
                        "service_emails": c.get("service_emails", False),
                        "news": c.get("news", False)})
        return out


def users_csv(news_only: bool = False) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "email", "phone", "teams", "service_emails", "news", "joined"])
    for u in all_users():
        if news_only and not u["news"]:
            continue
        w.writerow([u["name"], u["email"], u["phone"] or "", "; ".join(u["teams"]),
                    "yes" if u["service_emails"] else "no", "yes" if u["news"] else "no",
                    u["created_at"].strftime("%Y-%m-%d") if u["created_at"] else ""])
    return buf.getvalue()


def team_of(user_id: int, tournament_id: str) -> str | None:
    with db.session() as s:
        m = s.scalar(select(Membership).where(Membership.user_id == user_id,
                                              Membership.tournament_id == tournament_id))
        return m.owner_name if m else None

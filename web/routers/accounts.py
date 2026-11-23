"""Owner accounts: join links, account page, privacy, admin People page."""
import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

import accounts
import tournaments
from storage import load_teams
from web.auth import User, get_current_user, login_owner, require_auth

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
templates.env.globals["all_tournaments"] = tournaments.all_tournaments


def _admin(user: User = Depends(require_auth)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    return user


def _owners(t) -> list:
    return sorted(load_teams(t).get("teams", {}).keys())


def _landing(t_id: str) -> str:
    t = tournaments.get(t_id)
    return t.dashboard_prefix if t else "/"


# ── Join links ───────────────────────────────────────────────────────────────

@router.get("/join/{token}", response_class=HTMLResponse)
async def join_page(token: str, request: Request):
    inv = accounts.lookup_invite(token)
    user = get_current_user(request)
    ctx = {"user": user, "token": token, "inv": inv, "purposes": accounts.PURPOSES,
           "tournament": tournaments.get(inv["tournament_id"]) if inv else None}
    # Never log in on GET: WhatsApp fetches links for previews and would use them up.
    if inv and inv["state"] != "open" and user and user.is_owner \
            and inv["claimed_by"] == user.id:
        return RedirectResponse(_landing(inv["tournament_id"]), status_code=303)
    return templates.TemplateResponse(request=request, name="join.html", context=ctx,
                                      status_code=200 if inv else 404)


@router.post("/join/{token}", response_class=HTMLResponse)
async def join_submit(token: str, request: Request,
                      name: str = Form(""), email: str = Form(""), phone: str = Form(""),
                      service_emails: str | None = Form(None), news: str | None = Form(None),
                      privacy_ok: str | None = Form(None)):
    inv = accounts.lookup_invite(token)
    user = get_current_user(request)
    current = user.id if user and user.is_owner else None
    if inv and inv["state"] == "open" and inv["relogin"]:
        try:
            uid = accounts.use_relogin(token)
        except accounts.ClaimError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        login_owner(request, uid)
        return RedirectResponse(_landing(inv["tournament_id"]), status_code=303)
    try:
        if not current and not privacy_ok:
            raise accounts.ClaimError("Please tick the box to say you've read the privacy notice.")
        uid = accounts.claim(token, name, email, phone, bool(service_emails), bool(news),
                             current_user_id=current)
    except accounts.ClaimError as exc:
        return templates.TemplateResponse(
            request=request, name="join.html", status_code=400,
            context={"user": user, "token": token, "inv": inv, "error": str(exc),
                     "purposes": accounts.PURPOSES,
                     "tournament": tournaments.get(inv["tournament_id"]) if inv else None,
                     "form": {"name": name, "email": email, "phone": phone,
                              "service_emails": bool(service_emails), "news": bool(news)}})
    login_owner(request, uid)
    return RedirectResponse(_landing(inv["tournament_id"]) + "?welcome=1", status_code=303)


# ── Owner's own account ──────────────────────────────────────────────────────

@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, user: User = Depends(require_auth), saved: int = 0):
    if not user.is_owner:
        return RedirectResponse("/", status_code=303)
    profile = accounts.get_profile(user.id)
    teams = [{**tm, "tournament": tournaments.get(tm["tournament_id"])} for tm in profile["teams"]]
    return templates.TemplateResponse(request=request, name="account.html", context={
        "user": user, "profile": profile, "teams": teams, "purposes": accounts.PURPOSES,
        "saved": saved, "page": "account"})


@router.post("/account")
async def account_save(request: Request, user: User = Depends(require_auth),
                       name: str = Form(""), phone: str = Form(""),
                       service_emails: str | None = Form(None), news: str | None = Form(None)):
    if not user.is_owner:
        raise HTTPException(status_code=403)
    accounts.update_profile(user.id, name, phone,
                            {"service_emails": bool(service_emails), "news": bool(news)})
    return RedirectResponse("/account?saved=1", status_code=303)


@router.post("/account/delete")
async def account_delete(request: Request, user: User = Depends(require_auth),
                         confirm: str = Form("")):
    if not user.is_owner:
        raise HTTPException(status_code=403)
    if confirm.strip().upper() != "DELETE":
        return RedirectResponse("/account?saved=0", status_code=303)
    accounts.delete_user(user.id)
    request.session.clear()
    return RedirectResponse("/auth/login?deleted=1", status_code=303)


@router.get("/account/data.json")
async def account_data(user: User = Depends(require_auth)):
    """Everything we hold about this person (DPDP right to access)."""
    if not user.is_owner:
        raise HTTPException(status_code=403)
    p = accounts.get_profile(user.id)
    body = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in p.items()}
    body["consent_log"] = [{**c, "at": c["at"].isoformat()} for c in p["consent_log"]]
    return JSONResponse(body, headers={"Content-Disposition": "attachment; filename=gullyxi-my-data.json"})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={
        "user": get_current_user(request), "purposes": accounts.PURPOSES,
        "version": accounts.NOTICE_VERSION})


# ── Admin: People ────────────────────────────────────────────────────────────

@router.get("/admin/people", response_class=HTMLResponse)
async def people_page(request: Request, user: User = Depends(_admin)):
    groups = []
    for t in tournaments.all_tournaments():
        owners = _owners(t)
        groups.append({"t": t, "rows": accounts.team_status(t.id, owners) if owners else []})
    return templates.TemplateResponse(request=request, name="admin_people.html", context={
        "user": user, "groups": groups, "users": accounts.all_users(), "page": "people"})


@router.post("/admin/people/invite")
async def people_invite(tid: str = Form(...), owner: str = Form(...), user: User = Depends(_admin)):
    t = tournaments.get(tid)
    if t is None or owner not in _owners(t):
        raise HTTPException(status_code=404, detail="Unknown tournament or team")
    token = accounts.create_invite(t.id, owner)
    # the page builds the full URL from its own address, so a new domain needs no change
    return JSONResponse({"path": f"/join/{token}", "owner": owner, "tournament": t.name,
                         "relogin": accounts.lookup_invite(token)["relogin"]})


@router.post("/admin/people/release")
async def people_release(tid: str = Form(...), owner: str = Form(...), user: User = Depends(_admin)):
    accounts.release_team(tid, owner)
    return JSONResponse({"status": "released"})


@router.post("/admin/people/delete-user")
async def people_delete_user(user_id: int = Form(...), user: User = Depends(_admin)):
    accounts.delete_user(user_id)
    return JSONResponse({"status": "deleted"})


@router.get("/admin/people/emails.csv")
async def people_csv(news_only: int = 0, user: User = Depends(_admin)):
    name = "gullyxi-news-optin.csv" if news_only else "gullyxi-users.csv"
    return Response(accounts.users_csv(news_only=bool(news_only)), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}"})

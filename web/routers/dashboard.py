"""Dashboard routes - main views for scores and analytics."""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from config import LeagueConfig
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
templates.env.globals["all_tournaments"] = tournaments.all_tournaments
import team_names as _tn
templates.env.globals["team_name"] = _tn.display
templates.env.globals["team_names"] = _tn.names


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

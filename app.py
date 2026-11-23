#!/usr/bin/env python3
"""
IPL Fantasy Premier League 2026 – FastAPI Web Application

This web interface provides authenticated access to fantasy scores,
leaderboards, match details, and downloadable reports.
"""
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import configuration (uses environment variables)
try:
    from config_prod import *
    from config_prod import validate_production_config
except ImportError:
    from config import *
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

from starlette.middleware.cors import CORSMiddleware

try:
    from web.auth import get_current_user, User
    from web.routers import dashboard, downloads, auth as auth_router, api as api_router, public as public_router
    from web.logger import setup_logging, get_logger
    import tournaments
    from web.services import get_leaderboard_data, get_dashboard_stats, get_match_history_data, get_season_form
except Exception as _import_err:
    import traceback
    print(f"FATAL: Failed to import web modules: {_import_err}")
    traceback.print_exc()
    raise

# ══════════════════════════════════════════════════════════════
# LOGGING SETUP
# ══════════════════════════════════════════════════════════════

if 'LOG_LEVEL' in dir() and 'LOG_FILE' in dir():
    app_logger = setup_logging(
        log_level=LOG_LEVEL,
        log_file=LOG_FILE,
        app_name="ipl_fantasy"
    )
else:
    app_logger = setup_logging(log_level="INFO", app_name="ipl_fantasy")

logger = get_logger("app")

# ══════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ══════════════════════════════════════════════════════════════

# Initialize FastAPI app
app = FastAPI(
    title="Gully XI",
    description="Fantasy cricket scoring and leaderboard system",
    version="1.0.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,  # Disable docs in prod
    redoc_url="/redoc" if ENVIRONMENT == "development" else None,
)

logger.info(f"Starting application in {ENVIRONMENT} mode")

# ══════════════════════════════════════════════════════════════
# MIDDLEWARE SETUP
# ══════════════════════════════════════════════════════════════

# Session middleware for authentication (must be added before other middleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=f"ipl_fantasy_session_{ENVIRONMENT}",
    max_age=SESSION_MAX_AGE if 'SESSION_MAX_AGE' in dir() else 3600 * 24 * 7,
    same_site=SESSION_COOKIE_SAMESITE if 'SESSION_COOKIE_SAMESITE' in dir() else "lax",
    https_only=SESSION_COOKIE_SECURE if 'SESSION_COOKIE_SECURE' in dir() else False,
)

# Simple CORS - allow all origins (Railway handles HTTPS/security at proxy level)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = None

# ══════════════════════════════════════════════════════════════
# STATIC FILES
# ══════════════════════════════════════════════════════════════

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "web", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "web", "templates")
templates = Jinja2Templates(directory=templates_dir)
templates.env.globals["all_tournaments"] = tournaments.all_tournaments

# ══════════════════════════════════════════════════════════════
# ROUTERS
# ══════════════════════════════════════════════════════════════

# Include routers
app.include_router(auth_router.router, prefix="/auth", tags=["authentication"])
# One set of dashboard pages per tournament, e.g. /ipl/2026, /wwc/2026, /wpl/2027
for _t in tournaments.all_tournaments():
    app.include_router(dashboard.router, prefix=_t.dashboard_prefix, tags=[_t.id])
    logger.info(f"Tournament {_t.id} ({_t.status}) at {_t.dashboard_prefix}")
app.include_router(downloads.router, prefix="/downloads", tags=["downloads"])
app.include_router(api_router.router, prefix="/api", tags=["api"])
app.include_router(public_router.router, prefix="/api/public", tags=["public"])

logger.info("Routers registered successfully")


@app.middleware("http")
async def legacy_url_redirect(request: Request, call_next):
    """Old single-league URLs (/dashboard/..., /wwc/...) -> /ipl/2026/..., /wwc/2026/..."""
    new_path = tournaments.legacy_redirect(request.url.path)
    if new_path:
        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(url=new_path + query, status_code=301)
    return await call_next(request)

# ══════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/")
async def root(request: Request):
    """Home page – league selector if logged in, else redirect to login."""
    username = request.session.get("username")
    if not username:
        return RedirectResponse(url="/auth/login", status_code=302)

    groups = []
    for label, items in tournaments.grouped():
        groups.append({
            "label": label,
            "tournaments": [
                {"config": t,
                 "stats": get_dashboard_stats(t),
                 "leaderboard": get_leaderboard_data(t)}
                for t in items
            ],
        })

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"user": {"username": username}, "groups": groups,
                 "featured": _featured_tournament(groups),
                 "upcoming": _next_tournament(groups)},
    )


def _featured_tournament(groups):
    """The tournament the home page leads with: a live one with matches,
    otherwise the most recently finished one. None if nothing has been scored."""
    items = [it for g in groups for it in g["tournaments"] if it["stats"]["total_matches"] > 0]
    if not items:
        return None
    live = [it for it in items if it["config"].status == "live"]
    pick = live[0] if live else max(items, key=lambda it: it["config"].end_date or "")
    t = pick["config"]
    history = get_match_history_data(t)  # newest first
    latest = None
    if history:
        m = history[0]
        ranked = sorted(m.get("team_scores", {}).items(), key=lambda x: x[1], reverse=True)
        latest = {
            "label": m.get("match_number_label") or "Latest match",
            "description": m.get("description", ""),
            "date": m.get("date_str", ""),
            "top": [{"team": k, "points": v, "place": 1 + sum(1 for _, o in ranked if o > v)}
                    for k, v in ranked[:3]],
            "margin": round(ranked[0][1] - ranked[1][1], 2) if len(ranked) > 1 else 0,
            "match_id": m.get("match_id"),
        }
    board = pick["leaderboard"]
    return {
        "config": t,
        "leaderboard": board,
        "stats": pick["stats"],
        "lead_margin": round(board[0]["points"] - board[1]["points"], 2) if len(board) > 1 else 0,
        "form": get_season_form(t),
        "latest": latest,
    }


def _next_tournament(groups):
    """Soonest upcoming tournament with a start date, plus days to go."""
    from datetime import date
    best = None
    for g in groups:
        for it in g["tournaments"]:
            t = it["config"]
            if t.status in ("upcoming", "auction") and t.start_date:
                try:
                    days = (date.fromisoformat(t.start_date) - date.today()).days
                except ValueError:
                    continue
                if best is None or days < best["days"]:
                    best = {"config": t, "days": days}
    return best


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns application status, version, and basic system info.
    """
    import psutil
    from datetime import datetime
    
    # Get system metrics (non-blocking - uses cached value from last interval)
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    health_data = {
        "status": "healthy",
        "service": "ipl-fantasy-league",
        "version": app.version,
        "environment": ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
        }
    }
    
    logger.debug(f"Health check: {health_data['status']}")
    return JSONResponse(content=health_data)


@app.get("/ping")
async def ping():
    """Simple ping endpoint for basic connectivity checks."""
    return {"ping": "pong"}


# ══════════════════════════════════════════════════════════════
# STARTUP/SHUTDOWN EVENTS
# ══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("="*60)
    logger.info("  Gully XI - Starting Up")
    logger.info(f"  Environment: {ENVIRONMENT}")
    logger.info(f"  Version: {app.version}")
    logger.info(f"  Debug Mode: {DEBUG if 'DEBUG' in dir() else False}")
    logger.info("="*60)
    
    # Validate production config if in production
    if ENVIRONMENT == "production" and 'validate_production_config' in dir():
        validate_production_config()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Application shutting down...")


# ══════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ══════════════════════════════════════════════════════════════

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    logger.warning(f"404 Not Found: {request.url.path}")
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"message": getattr(exc, "detail", None) or "Page not found", "status_code": 404},
        status_code=404
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors."""
    logger.error(f"500 Internal Server Error: {request.url.path}", exc_info=exc)
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"message": "Internal server error", "status_code": 500},
        status_code=500
    )


# ══════════════════════════════════════════════════════════════
# DEVELOPMENT SERVER
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=HOST if 'HOST' in dir() else "0.0.0.0",
        port=PORT if 'PORT' in dir() else 8000,
        reload=RELOAD if 'RELOAD' in dir() else True,
        log_level="info"
    )

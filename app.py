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

from web.auth import get_current_user, User
from web.routers import dashboard, downloads, auth as auth_router
from web.logger import setup_logging, get_logger
from web.middleware import setup_all_middleware

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
    title="IPL Fantasy Premier League 2026",
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

# Setup production middleware (security, logging, CORS, rate limiting)
limiter = setup_all_middleware(app, sys.modules[__name__])

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

# ══════════════════════════════════════════════════════════════
# ROUTERS
# ══════════════════════════════════════════════════════════════

# Include routers
app.include_router(auth_router.router, prefix="/auth", tags=["authentication"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(downloads.router, prefix="/downloads", tags=["downloads"])

logger.info("Routers registered successfully")

# ══════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint - simple response for Railway health."""
    return {"status": "ok", "message": "IPL Fantasy League 2026 API running", "service": "ipl-fantasy"}


@app.get("/login-redirect")
async def login_redirect(request: Request):
    """Redirect helper for authenticated access."""
    username = request.session.get("username")
    if username:
        logger.debug(f"User {username} accessing root, redirecting to dashboard")
        return RedirectResponse(url="/dashboard", status_code=302)
    logger.debug("Anonymous user accessing root, redirecting to login")
    return RedirectResponse(url="/auth/login", status_code=302)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns application status, version, and basic system info.
    """
    import psutil
    from datetime import datetime
    
    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
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
    logger.info(f"  IPL Fantasy League 2026 - Starting Up")
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
        context={"message": "Page not found", "status_code": 404},
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

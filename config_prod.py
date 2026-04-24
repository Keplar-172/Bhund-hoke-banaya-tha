"""
Production-specific configuration for IPL Fantasy League 2026.

This module extends config.py with production-ready settings including:
- Enhanced logging
- Security headers
- Rate limiting
- CORS configuration
- Production optimizations
"""
import os
import logging
from pathlib import Path

# Import base configuration
from config import *

# ══════════════════════════════════════════════════════════════
# PRODUCTION OVERRIDES
# ══════════════════════════════════════════════════════════════

# Disable auto-reload in production
if ENVIRONMENT == "production":
    RELOAD = False
    DEBUG = False

# ══════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ══════════════════════════════════════════════════════════════

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("LOG_FILE", "logs/app.log")

# Create logs directory if it doesn't exist
if LOG_FILE:
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

# Logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ══════════════════════════════════════════════════════════════
# SECURITY SETTINGS
# ══════════════════════════════════════════════════════════════

# Rate limiting
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "60"))  # requests per minute
RATE_LIMIT_STORAGE = "memory"  # or "redis" for distributed setups

# CORS (Cross-Origin Resource Sharing)
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
if "*" in CORS_ORIGINS:
    CORS_ORIGINS = ["*"]
else:
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS]

# HTTPS settings
FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "false").lower() == "true"

# Session configuration
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"  # HTTPS only
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
SESSION_COOKIE_SAMESITE = "lax"  # CSRF protection
SESSION_MAX_AGE = 3600 * 24 * 7  # 7 days

# ══════════════════════════════════════════════════════════════
# PRODUCTION OPTIMIZATIONS
# ══════════════════════════════════════════════════════════════

# Cache settings
ENABLE_STATIC_FILE_CACHE = True
STATIC_FILE_MAX_AGE = 3600 * 24 * 30  # 30 days

# Gzip compression
ENABLE_GZIP = True
GZIP_MIN_SIZE = 500  # bytes

# ══════════════════════════════════════════════════════════════
# APPLICATION METADATA
# ══════════════════════════════════════════════════════════════

APP_NAME = "IPL Fantasy League 2026"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Fantasy cricket scoring system for IPL 2026"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@wizzlebin.com")

# ══════════════════════════════════════════════════════════════
# HEALTH CHECK CONFIGURATION
# ══════════════════════════════════════════════════════════════

HEALTH_CHECK_ENABLED = True
HEALTH_CHECK_PATH = "/health"

# ══════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════

def validate_production_config():
    """Validate critical production settings."""
    issues = []
    
    if ENVIRONMENT == "production":
        # Check for default SECRET_KEY
        if not os.environ.get("SECRET_KEY"):
            issues.append("SECRET_KEY must be set in environment variables for production")
        
        # Check for API key
        if not RAPIDAPI_KEY:
            issues.append("RAPIDAPI_KEY must be set for API functionality")
        
        # Check for HTTPS in production
        if not FORCE_HTTPS:
            issues.append("FORCE_HTTPS should be enabled in production with SSL")
        
        # Check for proper CORS configuration
        if "*" in CORS_ORIGINS:
            issues.append("CORS_ORIGINS should be specific in production (not wildcard)")
    
    if issues:
        print("\n⚠️  PRODUCTION CONFIGURATION WARNINGS:")
        for issue in issues:
            print(f"  - {issue}")
        print()
    
    return len(issues) == 0

# Validate on import in production
if ENVIRONMENT == "production":
    validate_production_config()

"""
Middleware for production security and performance.

Includes:
- Rate limiting
- Security headers
- Request logging
- HTTPS redirect
- CORS configuration
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# RATE LIMITING
# ══════════════════════════════════════════════════════════════

def setup_rate_limiter(app, rate_limit: str = "60/minute"):
    """
    Setup rate limiting for the application.
    
    Args:
        app: FastAPI application instance
        rate_limit: Rate limit string (e.g., "60/minute", "100/hour")
    """
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info(f"Rate limiting enabled: {rate_limit}")
    return limiter


# ══════════════════════════════════════════════════════════════
# SECURITY HEADERS MIDDLEWARE
# ══════════════════════════════════════════════════════════════

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        
        return response


# ══════════════════════════════════════════════════════════════
# REQUEST LOGGING MIDDLEWARE
# ══════════════════════════════════════════════════════════════

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with timing information."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                f"Response: {response.status_code} "
                f"for {request.method} {request.url.path} "
                f"[{duration:.3f}s]"
            )
            
            # Add response time header
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Error: {str(e)} "
                f"for {request.method} {request.url.path} "
                f"[{duration:.3f}s]",
                exc_info=True
            )
            raise


# ══════════════════════════════════════════════════════════════
# HTTPS REDIRECT MIDDLEWARE
# ══════════════════════════════════════════════════════════════

class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP requests to HTTPS in production."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Allow health check endpoint on HTTP (for Railway/platform health checks)
        if request.url.path == "/health":
            return await call_next(request)
        
        # Check if request is already HTTPS or from localhost
        if request.url.scheme == "https" or request.client.host in ["127.0.0.1", "localhost"]:
            return await call_next(request)
        
        # Redirect to HTTPS
        https_url = request.url.replace(scheme="https")
        logger.info(f"Redirecting to HTTPS: {https_url}")
        return RedirectResponse(url=str(https_url), status_code=301)


# ══════════════════════════════════════════════════════════════
# CORS SETUP
# ══════════════════════════════════════════════════════════════

def setup_cors(app, allowed_origins: list):
    """
    Setup CORS middleware.
    
    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origins
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info(f"CORS enabled for origins: {allowed_origins}")


# ══════════════════════════════════════════════════════════════
# MIDDLEWARE SETUP HELPER
# ══════════════════════════════════════════════════════════════

def setup_all_middleware(app, config):
    """
    Setup all middleware for the application.
    
    Args:
        app: FastAPI application instance
        config: Configuration module with settings
    """
    # 1. Security headers (always enabled)
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware enabled")
    
    # 2. Request logging (if not in test environment)
    if config.ENVIRONMENT != "test":
        app.add_middleware(RequestLoggingMiddleware)
        logger.info("Request logging middleware enabled")
    
    # 3. HTTPS redirect (only in production)
    if config.ENVIRONMENT == "production" and config.FORCE_HTTPS:
        app.add_middleware(HTTPSRedirectMiddleware)
        logger.info("HTTPS redirect middleware enabled")
    
    # 4. CORS
    if hasattr(config, 'CORS_ORIGINS'):
        setup_cors(app, config.CORS_ORIGINS)
    
    # 5. Rate limiting
    if hasattr(config, 'RATE_LIMIT'):
        limiter = setup_rate_limiter(app, f"{config.RATE_LIMIT}/minute")
        return limiter
    
    return None

"""
Logging configuration for IPL Fantasy League 2026.

Provides structured logging with:
- Console output (colored in development)
- File output (with rotation)
- JSON formatting option for production log aggregation
- Request/response logging
- Error tracking
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: str = None,
    app_name: str = "ipl_fantasy",
    json_logs: bool = False
):
    """
    Setup application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None to disable file logging)
        app_name: Application name for logger
        json_logs: Whether to use JSON formatting (useful for log aggregation)
    
    Returns:
        Configured logger instance
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger(app_name)
    logger.setLevel(numeric_level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # ═══════════════════════════════════════════════════════════
    # CONSOLE HANDLER
    # ═══════════════════════════════════════════════════════════
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # Console format (colored for better readability in development)
    console_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # ═══════════════════════════════════════════════════════════
    # FILE HANDLER (with rotation)
    # ═══════════════════════════════════════════════════════════
    
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler (10MB per file, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        
        # File format (more detailed)
        if json_logs:
            # JSON format for log aggregation tools (ELK, Datadog, etc.)
            file_format = logging.Formatter(
                fmt='{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"logger": "%(name)s", "module": "%(module)s", '
                    '"function": "%(funcName)s", "line": %(lineno)d, '
                    '"message": "%(message)s"}',
                datefmt="%Y-%m-%dT%H:%M:%S"
            )
        else:
            # Standard format
            file_format = logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | "
                    "%(module)s.%(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
        
        logger.info(f"File logging enabled: {log_file}")
    
    # ═══════════════════════════════════════════════════════════
    # STARTUP BANNER
    # ═══════════════════════════════════════════════════════════
    
    logger.info("=" * 60)
    logger.info(f"  {app_name.upper()} - Logging Initialized")
    logger.info(f"  Log Level: {log_level}")
    logger.info(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (defaults to calling module)
    
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(name)
    return logging.getLogger("ipl_fantasy")


# ══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════

def log_request(logger: logging.Logger, request, user: str = None):
    """Log an incoming HTTP request."""
    user_info = f"user={user}" if user else "anonymous"
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"[{user_info}] from {request.client.host if request.client else 'unknown'}"
    )


def log_response(logger: logging.Logger, request, response, duration: float):
    """Log an HTTP response with timing."""
    logger.info(
        f"Response: {response.status_code} for {request.method} {request.url.path} "
        f"[{duration:.3f}s]"
    )


def log_error(logger: logging.Logger, error: Exception, context: str = None):
    """Log an error with context."""
    context_str = f" ({context})" if context else ""
    logger.error(
        f"Error{context_str}: {type(error).__name__}: {str(error)}",
        exc_info=True
    )


def log_security_event(logger: logging.Logger, event: str, details: dict = None):
    """Log a security-related event."""
    details_str = f" | Details: {details}" if details else ""
    logger.warning(f"Security Event: {event}{details_str}")


# ══════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test logging setup
    logger = setup_logging(
        log_level="DEBUG",
        log_file="logs/test.log",
        app_name="test_app"
    )
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    try:
        1 / 0
    except Exception as e:
        log_error(logger, e, "Division by zero test")

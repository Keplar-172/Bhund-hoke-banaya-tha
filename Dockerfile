# Use Python 3.12 slim image (LTS, smaller footprint than 3.14)
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p data/scorecards logs "Match data"

# Non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (Railway uses dynamic PORT from environment)
# Do NOT set ENV PORT here - Railway provides it dynamically
EXPOSE 8000

# Health check disabled for Railway (Railway has its own health check)
# HEALTHCHECK is not supported by Railway's builder

# Run application with gunicorn (production-ready ASGI server)
# Use shell form to allow $PORT variable substitution from Railway
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info

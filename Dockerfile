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

# Create necessary directories and a read-only seed copy of data.
# data-seed is never mounted as a volume, so it always holds the
# latest committed data and acts as the initial state for the volume.
RUN mkdir -p data/scorecards logs "Match data" && \
    cp -r data data-seed

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (Railway uses dynamic PORT from environment)
# Do NOT set ENV PORT here - Railway provides it dynamically
EXPOSE 8000

# Health check disabled for Railway (Railway has its own health check)
# HEALTHCHECK is not supported by Railway's builder

# Entrypoint seeds missing data files from data-seed into the volume,
# then starts the app.
ENTRYPOINT ["./docker-entrypoint.sh"]

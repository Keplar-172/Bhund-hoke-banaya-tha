#!/bin/sh
# Docker entrypoint: seeds data files into the volume if they don't already exist.
# The volume is mounted at /app/data, which overrides the files baked into the image.
# We keep a read-only seed copy at /app/data-seed and copy files on first boot.

SEED_DIR="/app/data-seed"
DATA_DIR="/app/data"

echo "[entrypoint] Checking data directory at ${DATA_DIR}..."
mkdir -p "${DATA_DIR}/scorecards"

# Seed each file from data-seed if it doesn't exist on the volume
for src in "${SEED_DIR}"/*.json; do
    filename="$(basename "$src")"
    dest="${DATA_DIR}/${filename}"
    if [ ! -f "$dest" ]; then
        echo "[entrypoint] Seeding missing file: ${filename}"
        cp "$src" "$dest"
    else
        echo "[entrypoint] File already exists, skipping: ${filename}"
    fi
done

# Seed scorecard cache files
for src in "${SEED_DIR}/scorecards"/*.json; do
    [ -f "$src" ] || continue
    filename="$(basename "$src")"
    dest="${DATA_DIR}/scorecards/${filename}"
    if [ ! -f "$dest" ]; then
        echo "[entrypoint] Seeding scorecard: ${filename}"
        cp "$src" "$dest"
    fi
done

echo "[entrypoint] Data directory ready. Starting application..."
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info

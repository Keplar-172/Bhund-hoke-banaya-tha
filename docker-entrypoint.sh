#!/bin/sh
# Docker entrypoint: seeds data files into the volume if they don't already exist.
# The volume is mounted at /app/data, which overrides the files baked into the image.
# We keep a read-only seed copy at /app/data-seed and copy files on first boot.

SEED_DIR="/app/data-seed"
DATA_DIR="/app/data"

echo "[entrypoint] Checking data directory at ${DATA_DIR}..."
mkdir -p "${DATA_DIR}/scorecards"
mkdir -p "${DATA_DIR}/wwc/scorecards"

# Seed each top-level IPL file from data-seed if missing or empty
for src in "${SEED_DIR}"/*.json; do
    filename="$(basename "$src")"
    dest="${DATA_DIR}/${filename}"
    if [ ! -f "$dest" ] || [ ! -s "$dest" ]; then
        echo "[entrypoint] Seeding: ${filename}"
        cp "$src" "$dest"
    else
        echo "[entrypoint] Already exists, skipping: ${filename}"
    fi
done

# Seed IPL scorecard cache files
for src in "${SEED_DIR}/scorecards"/*.json; do
    [ -f "$src" ] || continue
    filename="$(basename "$src")"
    dest="${DATA_DIR}/scorecards/${filename}"
    if [ ! -f "$dest" ] || [ ! -s "$dest" ]; then
        echo "[entrypoint] Seeding scorecard: ${filename}"
        cp "$src" "$dest"
    fi
done

# Seed WWC data files (teams, players, and any pre-existing scores)
for src in "${SEED_DIR}/wwc"/*.json; do
    [ -f "$src" ] || continue
    filename="$(basename "$src")"
    dest="${DATA_DIR}/wwc/${filename}"
    if [ ! -f "$dest" ] || [ ! -s "$dest" ]; then
        echo "[entrypoint] Seeding WWC: ${filename}"
        cp "$src" "$dest"
    else
        echo "[entrypoint] WWC already exists, skipping: ${filename}"
    fi
done

# Seed WWC scorecard cache files
for src in "${SEED_DIR}/wwc/scorecards"/*.json; do
    [ -f "$src" ] || continue
    filename="$(basename "$src")"
    dest="${DATA_DIR}/wwc/scorecards/${filename}"
    if [ ! -f "$dest" ] || [ ! -s "$dest" ]; then
        echo "[entrypoint] Seeding WWC scorecard: ${filename}"
        cp "$src" "$dest"
    fi
done

echo "[entrypoint] Data directory ready. Starting application..."
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info

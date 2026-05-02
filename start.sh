#!/bin/bash
set -e

# Seed the volume with bundled data if it is empty (first deploy with volume attached)
if [ -d /app/data_seed ] && [ -z "$(ls -A /app/data 2>/dev/null)" ]; then
    echo "Volume at /app/data is empty — seeding with bundled data..."
    cp -r /app/data_seed/. /app/data/
    echo "Seed complete: $(ls /app/data)"
else
    echo "Volume already has data — skipping seed."
fi

exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info

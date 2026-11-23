#!/bin/sh
# Docker entrypoint. The Railway volume is mounted at /app/data and hides the
# data baked into the image; /app/data-seed keeps a read-only copy of it.
# bootstrap.py migrates the volume to the tournament layout (once) and seeds
# missing files from data-seed, then the app starts.
set -e

python bootstrap.py --data /app/data --seed /app/data-seed

exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info

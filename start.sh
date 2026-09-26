#!/bin/sh
set -e

echo "Initializing database..."
python -c "from app.db import init_db; init_db()"

if [ "${SEED_ON_START:-true}" = "true" ]; then
  echo "Running idempotent demo seed..."
  python seed.py
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

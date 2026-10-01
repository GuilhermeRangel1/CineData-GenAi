#!/bin/sh
set -eu

alembic upgrade head
python -m app.db.gold_seed \
  --database-url "${DATABASE_URL}" \
  --gold-database "${GOLD_DATABASE_PATH:-/app/data/cinerocket.db}"

if [ -n "${TMDB_API_TOKEN:-}" ]; then
  python -m app.db.enrich_home_trailers
fi

if [ -n "${INITIAL_ADMIN_EMAIL:-}" ] || [ -n "${INITIAL_ADMIN_NAME:-}" ] || [ -n "${INITIAL_ADMIN_PASSWORD:-}" ]; then
  python -m app.users.bootstrap_admin
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

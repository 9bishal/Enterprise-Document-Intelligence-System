#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1

# SQLite/Chroma/uploads live under these directories. They are gitignored, so
# a fresh Render checkout does not contain them.
mkdir -p data uploads

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# One Gunicorn worker with threads: SQLite and Chroma's PersistentClient are
# not safe for multiple writer processes. Scale by upgrading the datastores
# before increasing GUNICORN_WORKERS.
exec gunicorn django_backend.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
  --keep-alive "${GUNICORN_KEEPALIVE:-5}" \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" \
  --access-logfile - \
  --error-logfile -

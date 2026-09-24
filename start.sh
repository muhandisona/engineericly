#!/bin/sh
set -e

mkdir -p "$DATA_DIR/vol/static" "$DATA_DIR/vol/media"

echo "🟢 Running migrations..."
python manage.py migrate --noinput

echo "🟢 Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "🟢 Starting gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level "${GUNICORN_LOG_LEVEL:-info}"

#!/bin/sh
set -e

echo ">>> Running migrations..."
python manage.py migrate --no-input

echo ">>> Collecting static files..."
python manage.py collectstatic --no-input --clear

echo ">>> Starting gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  admin_panel.wsgi:application

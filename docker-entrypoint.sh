#!/bin/sh
set -e

mkdir -p /app/staticfiles

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "$#" -gt 0 ]; then
    exec "$@"
else
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
fi
    
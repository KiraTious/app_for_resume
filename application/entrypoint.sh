#!/bin/bash
set -e

export FLASK_APP=${FLASK_APP:-app.py}

DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres}
DB_NAME=${DB_NAME:-fleettracker}

until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  echo "Waiting for database $DB_HOST:$DB_PORT..."
  sleep 2
done

echo "Database is available."
echo "Starting application..."

flask db upgrade

exec gunicorn -b 0.0.0.0:${PORT:-5000} app:app
#!/bin/bash
set -e

# DB가 준비될 때까지 대기
echo "Waiting for database..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

echo "Running DB Migrations..."
alembic upgrade head

echo "Starting Application..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

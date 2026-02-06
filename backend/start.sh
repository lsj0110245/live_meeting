#!/bin/bash

# DB가 준비될 때까지 잠시 대기 (선택 사항)
# echo "Waiting for database..."
# sleep 5

echo "Running DB Migrations..."
alembic upgrade head

echo "Starting Application..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

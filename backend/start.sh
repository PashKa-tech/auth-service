#!/bin/bash
set -e

# Run Alembic migrations
echo "Running database migrations..."
alembic upgrade head

# Start FastAPI application using Uvicorn
echo "Starting FastAPI server..."
uvicorn src.main:app --host 0.0.0.0 --port 8000

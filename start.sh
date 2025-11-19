#!/bin/bash
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting FastAPI application..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000


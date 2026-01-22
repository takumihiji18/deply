#!/bin/bash
set -e

echo "Starting FastAPI..."
echo "Python: $(python --version)"
echo "Directory: $(pwd)"

cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

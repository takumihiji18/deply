#!/bin/bash
set -e

echo "Starting FastAPI..."
echo "Python: $(python --version)"
echo "Directory: $(pwd)"

# Install dependencies
pip install -r requirements.txt

cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

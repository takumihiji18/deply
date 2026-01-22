#!/bin/bash
set -e

echo "=== Starting application ==="
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Проверка структуры
echo "=== Directory contents ==="
ls -la

# Зависимости уже установлены в Dockerfile, пропускаем pip install

echo "=== Starting FastAPI application ==="
cd backend
echo "Backend directory: $(pwd)"
ls -la

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

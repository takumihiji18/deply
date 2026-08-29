#!/usr/bin/env bash
set -euo pipefail

# Idempotent bootstrap for the Telegram Auto-Responder dev environment.
# Sets up the Python backend (FastAPI) and the React frontend.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# The default image ships Python without the venv module, so ensure it exists.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  echo "Installing python3-venv..."
  sudo apt-get update -qq
  PY_MINOR="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  sudo apt-get install -y -qq "python${PY_MINOR}-venv" || sudo apt-get install -y -qq python3-venv
fi

# Backend: isolated virtualenv + pinned requirements.
if [ ! -x ".venv/bin/python" ]; then
  echo "Creating Python virtualenv (.venv)..."
  python3 -m venv .venv
fi
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r backend/requirements.txt

# Frontend: npm dependencies.
echo "Installing frontend dependencies..."
npm --prefix frontend install

echo "Environment setup complete."

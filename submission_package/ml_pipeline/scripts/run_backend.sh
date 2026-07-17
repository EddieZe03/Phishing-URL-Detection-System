#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/workspaces/FYP"
LOG_DIR="$HOME/.local/state/phish-guard"
mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

# Prefer project virtualenv if available.
if [[ -x "/home/codespace/.python/current/bin/python3" ]]; then
  PYTHON_BIN="/home/codespace/.python/current/bin/python3"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "python3 not found in PATH" >&2
  exit 1
fi

export PORT="${PORT:-5000}"
export FLASK_ENV="production"

exec "$PYTHON_BIN" "$ROOT_DIR/app.py" >> "$LOG_DIR/backend.log" 2>&1

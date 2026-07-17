#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="$HOME/.local/state/phish-guard"
mkdir -p "$LOG_DIR"

CLOUDFLARED_BIN="$(command -v cloudflared || true)"
if [[ -z "$CLOUDFLARED_BIN" ]]; then
  echo "cloudflared is not installed or not in PATH" >&2
  exit 1
fi

# Quick tunnel URL stays active as long as this process is alive.
exec "$CLOUDFLARED_BIN" tunnel --url "http://127.0.0.1:5000" --no-autoupdate >> "$LOG_DIR/cloudflared.log" 2>&1

#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

PORT="${1:-8080}"
URL="http://127.0.0.1:$PORT/control.html"

mkdir -p output memory docs/data

echo "[MICELIO] Iniciando centro de control en $URL"

(
  sleep 2
  if command -v termux-open-url >/dev/null 2>&1; then
    termux-open-url "$URL" || true
  elif command -v am >/dev/null 2>&1; then
    am start -a android.intent.action.VIEW -d "$URL" >/dev/null 2>&1 || true
  else
    echo "[MICELIO] Abre manualmente: $URL"
  fi
) &

python runner/micelio/control_server.py

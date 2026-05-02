#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR/docs"

PORT="${1:-8080}"

echo "[MICELIO] Dashboard local disponible en: http://127.0.0.1:$PORT"
echo "[MICELIO] Abre esa URL desde Chrome en tu Android."
python -m http.server "$PORT"

#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "[MICELIO] Preparando entorno Termux..."

pkg update -y
pkg upgrade -y
pkg install -y git python nano openssh curl termux-api

python -m pip install --upgrade pip
pip install -r requirements.txt

mkdir -p output memory docs/data
chmod +x scripts/*.sh || true

echo "[MICELIO] Entorno listo."
echo "Siguiente paso: ./scripts/termux_control.sh"

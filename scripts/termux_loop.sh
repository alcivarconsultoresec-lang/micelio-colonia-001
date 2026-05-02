#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

CYCLES="${1:-10}"
SLEEP_SECONDS="${2:-30}"

if ! [[ "$CYCLES" =~ ^[0-9]+$ ]]; then CYCLES=10; fi
if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]]; then SLEEP_SECONDS=30; fi

if [ "$CYCLES" -lt 1 ]; then CYCLES=1; fi
if [ "$CYCLES" -gt 50 ]; then CYCLES=50; fi
if [ "$SLEEP_SECONDS" -lt 5 ]; then SLEEP_SECONDS=5; fi
if [ "$SLEEP_SECONDS" -gt 300 ]; then SLEEP_SECONDS=300; fi

echo "[MICELIO] Loop Termux: $CYCLES ciclo(s), pausa $SLEEP_SECONDS segundo(s)."

for i in $(seq 1 "$CYCLES"); do
  echo "[MICELIO] Ciclo $i/$CYCLES"
  ./scripts/termux_run_once.sh
  if [ "$i" -lt "$CYCLES" ]; then
    sleep "$SLEEP_SECONDS"
  fi
done

echo "[MICELIO] Loop finalizado."

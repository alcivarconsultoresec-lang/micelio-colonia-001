#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

export MICELIO_MAX_VIRTUAL_SPORES="${MICELIO_MAX_VIRTUAL_SPORES:-64}"
export MICELIO_MAX_CHILDREN_PER_CYCLE="${MICELIO_MAX_CHILDREN_PER_CYCLE:-3}"
export MICELIO_MAX_SURVIVORS="${MICELIO_MAX_SURVIVORS:-24}"
export MICELIO_MAX_ACTIVE_CANDIDATES="${MICELIO_MAX_ACTIVE_CANDIDATES:-5}"
export MICELIO_MODEL="${MICELIO_MODEL:-openai/gpt-4o-mini}"
export MICELIO_MAX_TOKENS="${MICELIO_MAX_TOKENS:-500}"
export MICELIO_AUTO_PUSH="${MICELIO_AUTO_PUSH:-false}"
export MICELIO_BATCH_MODE="${MICELIO_BATCH_MODE:-false}"

python runner/espora_runner.py

if [ "$MICELIO_BATCH_MODE" = "true" ]; then
  echo "[MICELIO] Batch mode activo: commit diferido hasta terminar el loop."
  echo "[MICELIO] Ejecución terminada."
  exit 0
fi

# Identidad local para commits generados desde Termux. No requiere credenciales de GitHub.
git config user.name "micelio-termux" >/dev/null
git config user.email "micelio-termux@local" >/dev/null

git add output/*.json memory/*.json memory/*.jsonl docs/data/*.json 2>/dev/null || true

if git diff --cached --quiet; then
  echo "[MICELIO] Sin cambios para guardar."
else
  git commit -m "Ejecución Termux MICELIO" || true

  if [ "$MICELIO_AUTO_PUSH" = "true" ]; then
    git push || echo "[MICELIO] No se pudo hacer push automático. Revisa autenticación GitHub."
  else
    echo "[MICELIO] Commit local creado. Push omitido para evitar pedir usuario/token en Termux."
    echo "[MICELIO] Para subir manualmente: git push"
  fi
fi

echo "[MICELIO] Ejecución terminada."

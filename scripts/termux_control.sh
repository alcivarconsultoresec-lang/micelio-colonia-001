#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

while true; do
  clear
  echo "========================================"
  echo " MICELIO CONTROL - Termux"
  echo "========================================"
  echo "1) Ejecutar 1 ciclo"
  echo "2) Ejecutar loop acelerado: 10 ciclos / 30s"
  echo "3) Ejecutar loop intensivo seguro: 20 ciclos / 10s"
  echo "4) Abrir dashboard local en puerto 8080"
  echo "5) Ver último resultado"
  echo "6) Ver métricas de colonia"
  echo "7) Git pull"
  echo "8) Salir"
  echo "========================================"
  read -r -p "Elige una opción: " option

  case "$option" in
    1)
      ./scripts/termux_run_once.sh
      read -r -p "Enter para continuar..." _
      ;;
    2)
      ./scripts/termux_loop.sh 10 30
      read -r -p "Enter para continuar..." _
      ;;
    3)
      ./scripts/termux_loop.sh 20 10
      read -r -p "Enter para continuar..." _
      ;;
    4)
      ./scripts/termux_server.sh 8080
      ;;
    5)
      cat output/resultados.json 2>/dev/null || echo "No existe output/resultados.json todavía."
      read -r -p "Enter para continuar..." _
      ;;
    6)
      cat output/colony_metrics.json 2>/dev/null || cat docs/data/metrics.json 2>/dev/null || echo "No existen métricas todavía."
      read -r -p "Enter para continuar..." _
      ;;
    7)
      git pull --rebase
      read -r -p "Enter para continuar..." _
      ;;
    8)
      exit 0
      ;;
    *)
      echo "Opción inválida."
      sleep 1
      ;;
  esac
done

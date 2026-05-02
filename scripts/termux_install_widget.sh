#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WIDGET_DIR="$HOME/.shortcuts"

mkdir -p "$WIDGET_DIR"

cat > "$WIDGET_DIR/MICELIO Control.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$REPO_DIR"
./scripts/termux_control.sh
EOF

cat > "$WIDGET_DIR/MICELIO Dashboard.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$REPO_DIR"
./scripts/termux_server.sh 8080
EOF

cat > "$WIDGET_DIR/MICELIO 1 Ciclo.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$REPO_DIR"
./scripts/termux_run_once.sh
EOF

cat > "$WIDGET_DIR/MICELIO Loop 10.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$REPO_DIR"
./scripts/termux_loop.sh 10 10
EOF

cat > "$WIDGET_DIR/MICELIO Roles.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$REPO_DIR"
cat output/roles_report.json 2>/dev/null || cat docs/data/roles.json 2>/dev/null || echo "Todavía no existe reporte de roles. Ejecuta un ciclo."
read -r -p "Enter para cerrar..." _
EOF

chmod +x "$WIDGET_DIR"/*.sh

echo "[MICELIO] Accesos Termux:Widget instalados en $WIDGET_DIR"
echo "Agrega el widget de Termux a la pantalla principal de Android y elige el acceso MICELIO que quieras."

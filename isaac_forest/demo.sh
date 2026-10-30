#!/usr/bin/env bash
# Demo para la exposición: Isaac Sim simula el bosque y los sensores, y Rerun lo muestra en vivo.
#   ./demo.sh            Isaac sin ventana + visor Rerun en vivo
#   ./demo.sh gui        Isaac con ventana (nube LiDAR dibujada en el viewport) + visor Rerun en vivo
#   ./demo.sh web        igual que el primero, pero el visor se abre en el navegador
#   ./demo.sh replay     sin Isaac: reproduce la grabación recordings/v2_bosque (plan B)
# Mundo: por defecto v2 (scenes/forest_v2_bosque.usd). WORLD=forest_v1_arboles ./demo.sh: v1 (solo árboles).
set -e
cd "$(dirname "$0")"
# Python de Isaac Sim 6.2 (ver README) y del visor (.venv_viz, ver README)
ISAAC_PY=${ISAAC_PY:-python}
VIZ_PY=${VIZ_PY:-.venv_viz/bin/python}
export OMNI_KIT_ACCEPT_EULA=YES
MODE=${1:-live}

if [ "$MODE" = "replay" ]; then
    exec $VIZ_PY viewer.py recordings/v2_bosque --replay
fi

OUT=recordings/live
rm -rf "$OUT"
mkdir -p "$OUT"
EXTRA=""
[ "$MODE" = "gui" ] && EXTRA="--gui"
# --duration 0: da vueltas sin fin; --keep: solo guarda los últimos 600 fotogramas (no llena el disco)
WORLD=${WORLD:-forest_v2_bosque}
$ISAAC_PY run_sensors.py --scene scenes/$WORLD.usd --duration 0 --keep 600 --out "$OUT" $EXTRA > "$OUT.log" 2>&1 &
ISAAC_PID=$!
trap 'kill $ISAAC_PID 2>/dev/null' EXIT
VIEW_ARGS=""
[ "$MODE" = "web" ] && VIEW_ARGS="--web"
$VIZ_PY viewer.py "$OUT" $VIEW_ARGS

#!/usr/bin/env bash
# Parte 3: datos de sensores. Una vuelta (84 s simulados, 840 fotogramas) por cada versión,
# capturas, comparación v1/v2 (tabla y figuras del paper) y videos de muestra.
# Requiere: scripts/03_build_scenes.sh, ISAAC_PY y el entorno del visor (.venv_viz). ~8 min en una RTX 5070 Ti.
set -euo pipefail
cd "$(dirname "$0")/../isaac_forest"
: "${ISAAC_PY:?Define ISAAC_PY con el python del entorno de Isaac Sim 6.2 (ver README)}"
export OMNI_KIT_ACCEPT_EULA=YES
for V in v1_arboles v2_bosque; do
    $ISAAC_PY run_sensors.py --scene scenes/forest_$V.usd --duration 84 --out recordings/$V
    $ISAAC_PY tools/screenshots.py --scene scenes/forest_$V.usd --out screenshots/$V
done
python3 tools/compare_worlds.py                  # recordings/comparacion_v1_v2.json + paper/figs/*_v1_v2.*
for V in v1_arboles v2_bosque; do
    python3 tools/make_video.py recordings/$V --out videos/$V.mp4
done

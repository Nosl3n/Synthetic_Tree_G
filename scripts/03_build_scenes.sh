#!/usr/bin/env bash
# Parte 2: escenas de Isaac Sim. Descarga los recursos CC0 de Poly Haven y construye
#   v1: scenes/forest_v1_arboles.usd (solo árboles)   v2: scenes/forest_v2_bosque.usd (bosque ambientado)
# Requiere: scripts/02_run_synth_trees.sh (usa work/syn_recombine y work/syn_procedural) y ISAAC_PY.
set -euo pipefail
cd "$(dirname "$0")/../isaac_forest"
: "${ISAAC_PY:?Define ISAAC_PY con el python del entorno de Isaac Sim 6.2 (ver README)}"
python3 tools/download_assets.py
$ISAAC_PY build_forest.py --bare --out scenes/forest_v1_arboles.usd
$ISAAC_PY build_forest.py --out scenes/forest_v2_bosque.usd

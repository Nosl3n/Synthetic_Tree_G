#!/usr/bin/env bash
# Parte 1: árboles sintéticos. Extrae rasgos de los 201 QSM, genera G0–G6 (760 árboles cada uno),
# evalúa frente a los árboles de test y produce las tablas y figuras del paper.
# Requiere: requirements.txt y scripts/01_download_data.sh. Tiempo: ~3 min con 32 núcleos.
set -euo pipefail
cd "$(dirname "$0")/../synth_trees"
PY=${PY:-python3}
$PY run_extract.py
$PY run_generate.py --gen iid_radius                                          # G0
$PY run_generate.py --gen allometric --params '{"alpha":0.25}' --tag a025     # G1 suave
$PY run_generate.py --gen allometric --params '{"alpha":0.5}'  --tag a050     # G1 fuerte
$PY run_generate.py --gen recombine                                           # G2
$PY run_generate.py --gen hybrid                                              # G3
$PY run_generate.py --gen procedural                                          # G4
$PY run_generate.py --gen rules                                               # G5
$PY run_generate.py --gen colonization                                        # G6
$PY evaluate.py                 # work/eval_summary.csv, eval_full.csv
$PY evaluate_mixtures.py        # work/eval_mixtures.csv
$PY data_stats.py               # work/data_stats.json
$PY make_figures.py             # paper/figs/{fidelidad_novedad.pdf, w1_rasgos.pdf, generadores.png}

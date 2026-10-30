#!/usr/bin/env bash
# Compila paper/main.pdf (requiere TeX Live con biber).
set -euo pipefail
cd "$(dirname "$0")/../paper"
latexmk -pdf -interaction=nonstopmode main.tex

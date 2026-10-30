# Datos externos (Google Drive)

Los archivos pesados se distribuyen aparte del repositorio. **Enlace: [Carpeta de Google Drive](https://drive.google.com/drive/folders/1A_rpW5E1f6_VL9n4JmHMmiPmwXZPpeNK?usp=sharing)**

Todos se pueden regenerar con `scripts/`. Descargarlos solo ahorra tiempo o sirve si no se tiene una GPU para Isaac Sim.

| Carpeta en Drive | Descomprimir en (desde la raíz del repo) | Para qué |
|---|---|---|
| `01_datos_sensores/v1_arboles.zip`, `v2_bosque.zip` | `isaac_forest/recordings/` | Datos etiquetados de LiDAR y cámara (formato en [DATOS.md](DATOS.md)). `./demo.sh replay` y `tools/compare_worlds.py` los usan |
| `02_rerun/*.rrd` | cualquier sitio | Ver un recorrido completo sin Isaac: `isaac_forest/.venv_viz/bin/rerun v2_bosque.rrd` |
| `03_videos/*.mp4` | — | Videos de muestra: cámara (RGB, profundidad, segmentación) y LiDAR (planta y alzado) |
| `04_escenas/escenas_v1_v2.zip` | `isaac_forest/scenes/` | Abrir las escenas en Isaac Sim (`File → Open`). Necesitan los recursos de Poly Haven: `python3 isaac_forest/tools/download_assets.py` |
| `05_arboles_sinteticos/work.zip` | `synth_trees/` (crea `synth_trees/work/`) | Árboles reales procesados, los 8 conjuntos sintéticos, rasgos y evaluaciones, sin ejecutar `02_run_synth_trees.sh` |
| `06_capturas/` | — | Capturas del simulador (v1 y v2) |

Después de colocar `05_arboles_sinteticos` se puede saltar directamente a `scripts/03_build_scenes.sh`.

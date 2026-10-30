# Formato de los datos

## Parte 1: `synth_trees/work/`

| Archivo | Contenido |
|---|---|
| `real/<árbol>.npz` | QSM real limpio (solo la parte conectada al cilindro 0): `start`, `axis`, `length`, `radius`, `parent`, `ext` |
| `real_trees.csv`, `real_branches.csv` | Rasgos por árbol (22 usados en la evaluación) y por rama |
| `split.csv` | Partición train/test por árbol (152/49, estratificada por especie, semilla 0) |
| `syn_<generador>[_tag]/<árbol>__<gen>_s<k>.npz` | Árbol sintético k (0–4) generado a partir del árbol de train `<árbol>`. Mismo formato que los reales |
| `syn_*/trees.csv`, `branches.csv` | Rasgos de los sintéticos. `source` es el árbol de origen y `meta` contiene los detalles del generador (JSON) |
| `eval_summary.csv`, `eval_full.csv` | Métricas por generador (resumen y detalle por rasgo) |
| `eval_mixtures.csv`, `data_stats.json` | Mezclas de generadores y descriptivos de los datos |

Los `.npz` se leen con `synth_trees/qsm.py`: `qsm.load_npz(ruta)` devuelve un `Tree` con rama, orden y posición recalculados.

## Partes 2 y 3: grabaciones de sensores (`isaac_forest/recordings/<versión>/`)

- `meta.json`: clases, sensores, intrínsecos de la cámara (`fx`, `fy`, `cx`, `cy`, `width`, `height`), circuito (`path_xy`), terreno (`terrain`) y lista de árboles (fuente, generador, especie, posición y rotación).
- `frames/NNNNNN.npz`: un fotograma cada 0,1 s de tiempo simulado.

| Clave | Tipo | Descripción |
|---|---|---|
| `lidar_xyz` | (N,3) float32 | Puntos del último barrido completo en coordenadas de mundo (m) |
| `lidar_xyz_sensor` | (N,3) float32 | Los mismos puntos en el marco del LiDAR |
| `lidar_intensity` | (N,) float16 | Intensidad del retorno |
| `lidar_label` | (N,) uint8 | Clase de cada punto (tabla abajo) |
| `lidar_tree` | (N,) int16 | Árbol alcanzado: 0–23 parcela, 100+ anillo exterior (v2), −1 si no es un árbol |
| `lidar_pose`, `cam_pose` | (4,4) float32 | Transformación local → mundo del LiDAR y de la cámara (convención columna: p_mundo = M · p) |
| `rgb` | (480,848,3) uint8 | Imagen |
| `depth` | (480,848) float16 | Distancia al plano imagen (m); 0 = cielo o fondo |
| `sem` | (480,848) uint8 | Clase de cada píxel |
| `t`, `lidar_t` | float64 | Tiempo simulado del fotograma y del barrido |
| `rig_xy`, `rig_yaw` | float32 | Posición y rumbo de la plataforma |

**Clases** (`lidar_label` y `sem`):

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| cielo / sin dato | suelo | tronco | rama | hoja (reservada, sin uso) | sotobosque | madera muerta | roca | otro |

La cámara es una cámara de pinhole sin distorsión. La convención de la cámara USD es: +X a la derecha, +Y arriba, mirando a −Z.

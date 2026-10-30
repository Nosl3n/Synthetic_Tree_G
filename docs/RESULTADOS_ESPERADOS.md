# Resultados esperados (para comprobar la replicación)

Valores obtenidos al ejecutar `scripts/01` → `04` desde cero, en un entorno limpio:
- Ubuntu 24.04, Python 3.12;
- `requirements.txt`;
- Isaac Sim 6.2.0.0;
- RTX 5070 Ti, driver 595.91.

| Paso | Tiempo |
|---|---|
| `01_download_data.sh` | 19 s |
| `02_run_synth_trees.sh` | 3 min (32 núcleos) |
| `03_build_scenes.sh` | 1 min (incluye descarga de recursos) |
| `04_record_sensors.sh` | 7,5 min |

## Parte 1: árboles sintéticos (deben coincidir exactamente)

Todas las semillas están fijadas. Dos ejecuciones independientes dieron archivos `.npz` **idénticos bit a bit** y métricas con diferencia 0.

`synth_trees/work/data_stats.json`:

| Dato | Valor |
|---|---|
| Árboles / especies / train / test | 201 / 53 / 152 / 49 |
| Altura (media ± d.e.) | 28,53 ± 5,13 m |
| Cilindros por árbol (mediana [RIC]) | 1785 [1115–3368] |
| Radio de cilindro (mediana [RIC]) | 2,72 [1,62–3,66] cm |
| Cilindros descartados (no conectados) | 0,56 % |
| Uniones de TreeQSM con hueco > 20 cm | 4,67 % (199 de 201 árboles) |
| Exponente de Leonardo Δ (train) | 2,382 |

`synth_trees/work/eval_summary.csv`:

| | Real (ref.) | G0 | G1 α=0,25 | G1 α=0,5 | G2 | G3 | G4 | G5 | G6 |
|---|---|---|---|---|---|---|---|---|---|
| 1-NNA | 0,455 | 0,542 | 0,570 | 0,651 | 0,559 | 0,559 | 0,632 | 0,892 | 0,978 |
| Novedad (`copia`) | 1,000 | 0,312 | 0,378 | 0,723 | 0,727 | 0,806 | 1,597 | 1,978 | 2,130 |
| W1n árbol (media) | 0,202 | 0,201 | 0,226 | 0,310 | 0,209 | 0,233 | 0,300 | 0,632 | 0,820 |
| W1n rama (media) | 0,039 | 0,042 | 0,052 | 0,075 | 0,049 | 0,061 | 0,063 | 0,096 | 0,312 |
| % ramas > madre | 5,82 | 12,03 | 5,12 | 5,24 | 5,67 | 5,01 | 5,54 | 0,00 | 0,00 |

`synth_trees/work/eval_mixtures.csv` (media de 5 semillas):

| | 1-NNA | Novedad | W1n árbol |
|---|---|---|---|
| Real train (ref.) | 0,475 ± 0,005 | 1,00 | 0,202 |
| G2 | 0,545 ± 0,005 | 0,73 | 0,209 |
| G4 | 0,607 ± 0,014 | 1,60 | 0,300 |
| G2+G4 | 0,546 ± 0,011 | 1,19 | 0,231 |
| G2+G3+G4 | 0,548 ± 0,011 | 1,01 | 0,227 |
| G2+G5 | 0,641 ± 0,006 | 1,41 | 0,360 |
| G2+G6 | 0,677 ± 0,009 | 1,66 | 0,465 |

## Parte 2: escenas (deben coincidir exactamente)

`isaac_forest/scenes/*_trees.json` es idéntico entre ejecuciones (árboles, posiciones, terreno, recorrido y objetos).

| Escena | Caras | Objetos |
|---|---|---|
| v1 | 2,36 M | — |
| v2 | 5,40 M | 110 árboles exteriores, 4 431 plantas, 835 piezas de madera muerta, 23 rocas |

## Parte 3: sensores (casi idénticos)

La cámara es determinista. El LiDAR RTX varía en menos del 0,01 % entre ejecuciones, por el orden de las operaciones en GPU. La velocidad depende del hardware.

`isaac_forest/recordings/comparacion_v1_v2.json`:

| | v1 | v2 |
|---|---|---|
| Fotogramas | 840 | 840 |
| Puntos LiDAR por barrido | ~60 097 | ~77 820 |
| LiDAR suelo / tronco / rama | 83,0 / 15,8 / 1,2 % | 52,0 / 17,6 / 7,2 % |
| LiDAR sotobosque / madera muerta / roca | — | 21,6 / 1,3 / 0,2 % |
| Cámara cielo / suelo / tronco / rama | 45,1 / 47,5 / 6,6 / 0,8 % | 36,2 / 40,1 / 9,2 / 4,8 % |
| Cámara sotobosque / madera muerta / roca | — | 9,0 / 0,6 / 0,1 % |
| Árboles de la parcela vistos por barrido | 23,85 | 23,85 |
| Puntos de tronco por árbol visto | ~398 | ~382 |
| Error del suelo LiDAR frente al terreno | 1 mm | 4 mm |
| Tiempo real por vuelta (RTX 5070 Ti) | ~145 s | ~196 s |

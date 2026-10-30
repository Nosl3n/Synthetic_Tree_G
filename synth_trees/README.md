# synth_trees: árboles sintéticos a partir de los QSM de BCI

Parte 1 del proyecto: Python puro (`requirements.txt`), sin GPU. Se ejecuta completa con `scripts/02_run_synth_trees.sh`. Las salidas van a `work/`.

## Pasos

```bash
python3 run_extract.py                      # limpia los QSM, cachea, mide rasgos, partición train/test
python3 run_generate.py --gen recombine     # un generador (ver lista abajo); 5 sintéticos por árbol de train
python3 evaluate.py                         # todos los generadores frente a test
python3 evaluate_mixtures.py                # mezclas de generadores
python3 data_stats.py                       # descriptivos de los datos
python3 make_figures.py                     # figuras del artículo
python3 render.py TRITUB_213134             # vista lateral de un árbol real y sus sintéticos
```

## Módulos

| Archivo | Contenido |
|---|---|
| `qsm.py` | Carga de `.mat` de TreeQSM y recálculo de la topología (rama/orden/posición) desde `parent`/`extension`; coincide al 100 % con TreeQSM. Codificación local tipo tortuga (`encode`/`decode`; error de ida y vuelta < 1e-6 m): cada cilindro se expresa en el marco de su padre, así se pueden cambiar radios, longitudes y ángulos o injertar ramas sin romper las uniones |
| `traits.py` | 22 rasgos por árbol y 5 por rama. Mismo código para reales y sintéticos |
| `generators.py` | G0–G6. Todos los estadísticos se ajustan **solo con train** |
| `evaluate.py` | W1 normalizada por rasgo, 1-NNA, novedad, % de ramas más gruesas que su madre y regla de tubería. Cada métrica se reporta junto a la referencia real (train frente a test) |

## Generadores

| | `--gen` | Idea |
|---|---|---|
| G0 | `iid_radius` | Radio de cada cilindro × U(0,9; 1,1). Línea base del repositorio `qsm-variation` |
| G1 | `allometric --params '{"alpha":0.25}' --tag a025` (y `0.5` / `a050`) | Por rama: radio y longitud log-normales de media 1 (ligados por la alometría longitud ~ radio^0,345), ángulos con ruido. Magnitud: α × variabilidad natural medida en train |
| G2 | `recombine` | Cada rama de orden 1, con p = 0,5, se sustituye por la de otro árbol de train de la misma especie, con altura y grosor parecidos y reescalada con la alometría |
| G3 | `hybrid` | G2 seguido de G1 con α = 0,25 |
| G4 | `procedural` | Árbol nuevo rama a rama: cada rama sortea la "regla" completa de una rama real de la misma especie y orden, condicionada al grosor de la madre |
| G5 | `rules` | Árbol nuevo solo con medias y dispersiones por especie y orden: alometrías, perfil de adelgazamiento, filotaxis de 137,5°, ángulos y densidad de ramas |
| G6 | `colonization` | *Space colonization* (Runions et al. 2007) en un elipsoide de copa, con radios por la regla de Leonardo (Δ = 2,38 medido en train) |

## Reproducibilidad

- **Semillas fijas:** partición (semilla 0) y una semilla por árbol sintético (`crc32(generador/árbol/k)`), así que cada árbol sintético no depende del orden de ejecución ni del número de procesos.
- **Comprobado:** una ejecución en un entorno limpio reproduce bit a bit los 6 080 árboles y todas las métricas.
- **Parámetros elegidos a mano:** solo dos, la ondulación de G4 (`wiggle_k=1`) y la densidad de puntos de G6 (`pts_per_m=1`). Se fijaron comparando con medianas de **train**, nunca de test.

## Limitaciones

- **Huecos de TreeQSM:** el 4,7 % de las uniones entre cilindros consecutivos tienen huecos de más de 20 cm (199 de 201 árboles). Los generadores que copian geometría real (G0–G4) los heredan.
- **No se comprueban intersecciones entre ramas.**
- **Los árboles no tienen hojas.**

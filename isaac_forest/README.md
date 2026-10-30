# isaac_forest: bosque virtual con LiDAR y cámara de profundidad (Isaac Sim 6.2)

Partes 2 y 3 del proyecto. Se ejecutan completas con `scripts/03_build_scenes.sh` y `scripts/04_record_sensors.sh`. Necesitan:
- `ISAAC_PY`: el python del entorno de Isaac Sim;
- `.venv_viz`: el entorno del visor (ver el README principal);
- los árboles sintéticos de la parte 1 (`../synth_trees/work/syn_recombine` y `syn_procedural`).

## Dos versiones del mismo bosque

Las dos tienen los mismos 24 árboles (12 G2 + 12 G4), en las mismas posiciones y con el mismo recorrido de la plataforma, así que sus datos se pueden comparar directamente.

| Versión | Escena | Contenido | Clases |
|---|---|---|---|
| **v1: solo árboles** | `scenes/forest_v1_arboles.usd` (`build_forest.py --bare`) | Árboles sobre suelo plano, cielo de campo | suelo, tronco, rama |
| **v2: bosque ambientado** | `scenes/forest_v2_bosque.usd` (`build_forest.py`) | Además: terreno ondulado con hojarasca, 110 árboles exteriores, ~4 400 plantas de sotobosque, ~840 piezas de madera muerta, rocas con musgo, cielo de selva | además, sotobosque, madera muerta y roca |

## Archivos

| Archivo | Qué hace |
|---|---|
| `meshing.py` | QSM → **un tubo continuo por rama**: cierra los huecos de TreeQSM, hace que las ramas hijas nazcan desde el eje de su madre, alisa el eje (Laplaciano proporcional al grosor + Chaikin) y usa marcos de transporte paralelo, normales suaves, UVs a lo largo de la rama y puntas cerradas |
| `dressing.py` | Terreno (suma de ondas), circuito de la plataforma, colocación de objetos de Poly Haven con *PointInstancer* (sin tocar troncos ni el circuito) |
| `build_forest.py` | Construye la escena USD y `<escena>_trees.json` (árboles, terreno, circuito, objetos) |
| `run_sensors.py` | Plataforma a 1 m/s con un **LiDAR Ouster OS1** (128 canales, 10 Hz, 1024 columnas, a 1,8 m) y una **cámara RGB-D** con la óptica de una Intel RealSense D455 (87°, 848×480, a 1,2 m). Guarda un fotograma etiquetado cada 0,1 s (formato en `../docs/DATOS.md`) |
| `viewer.py` | Visor Rerun: en vivo mientras Isaac graba, en reproducción (`--replay`), en el navegador (`--web`) o guardado a `.rrd` (`--save`) |
| `demo.sh` | Lanzador de la demostración: Isaac + visor en vivo, o solo reproducción |
| `tools/download_assets.py` | Descarga los recursos CC0 de Poly Haven (~450 MB) con verificación MD5 |
| `tools/screenshots.py` | Capturas del simulador desde 8 puntos de vista |
| `tools/compare_worlds.py` | Compara los datos de v1 y v2: tabla (`recordings/comparacion_v1_v2.json`) y figuras del artículo |
| `tools/make_video.py` | Video de una grabación: cámara (RGB, profundidad, segmentación) + LiDAR (planta y alzado) |
| `tools/probe_sensors.py` | Prueba mínima de que el LiDAR y la cámara funcionan en la instalación |

## Uso

```bash
export ISAAC_PY=~/isaacsim_env/bin/python OMNI_KIT_ACCEPT_EULA=YES
python3 tools/download_assets.py
$ISAAC_PY build_forest.py --bare --out scenes/forest_v1_arboles.usd
$ISAAC_PY build_forest.py --out scenes/forest_v2_bosque.usd
$ISAAC_PY run_sensors.py --scene scenes/forest_v2_bosque.usd --duration 84 --out recordings/v2_bosque
.venv_viz/bin/python viewer.py recordings/v2_bosque --replay
./demo.sh                      # Isaac + visor en vivo (v2). WORLD=forest_v1_arboles ./demo.sh para v1
```

Opciones útiles:
- `build_forest.py`: `--seed` (otro bosque), `--n-trees`, `--plot`, `--outer-trees`, `--hdri`, `--tubes` (versión antigua, un cilindro por segmento).
- `run_sensors.py`: `--speed`, `--rate`, `--lidar-variant` (cualquier variante del OS1 incluida en Isaac), `--res H W`, `--gui`, `--duration 0` (sin fin), `--keep K`.

## Clases y etiquetado

Cada malla y prototipo lleva una etiqueta `UsdSemantics` (`trunk`, `branch`, `ground`, `understory`, `deadwood`, `rock`).
- **Cámara:** la clase viene del anotador de segmentación semántica.
- **LiDAR:** se obtiene del identificador de objeto de cada retorno (`objId` + *stable-id map*), que da la ruta USD del objeto alcanzado; de ella salen la clase y el árbol.

Ninguna etiqueta se pone a mano.

## Limitaciones

- **Fondo de v2:** el bosque que se ve al fondo de la cámara es la foto del cielo HDRI. No tiene profundidad, se etiqueta como fondo y el LiDAR no lo ve. Para entrenar con la cámara, usa `--hdri farmland_overcast_2k.hdr` o enmascara el fondo.
- **Sensores ideales:** la profundidad no tiene ruido estereoscópico y el LiDAR no tiene reflectancia calibrada por material.
- **Velocidad:** la simulación va a ~0,6× (v1) y ~0,4× (v2) del tiempo real en una RTX 5070 Ti.
- **Sotobosque y madera muerta:** son modelos genéricos, no especies medidas en BCI.

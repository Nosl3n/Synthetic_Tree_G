# Synthetic_Tree_G

🌐 **English** · [Español](README.es.md)

**Generating synthetic tropical trees from real QSM tree models, with a virtual forest for LiDAR and depth-camera simulation in NVIDIA Isaac Sim.**

**Authors:** Nelson Broyer-Paco, Angel Marquez-Aguilar, Li Shi, Josine, Pacifique

📄 Paper: [`paper/main.pdf`](paper/main.pdf) (in Spanish) · 📦 Large files (recordings, videos, scenes): [Google Drive](https://drive.google.com/drive/folders/1A_rpW5E1f6_VL9n4JmHMmiPmwXZPpeNK?usp=sharing)

![The same forest in two versions](paper/figs/vistas_v1_v2.png)

---

## Summary

Networks that segment forest point clouds need large amounts of labelled data, and labelling is expensive. This project studies **how to generate realistic synthetic trees from real scanned trees** and **how to measure whether they resemble the real ones**. It then uses them to build a virtual forest with simulated sensors.

1. **Real data:** 201 QSMs (cylinder models reconstructed with TreeQSM) of tropical trees from 53 species on Barro Colorado Island, Panama ([Krishna Moorthy et al. 2022](https://doi.org/10.5281/zenodo.6981485), CC BY 4.0). They are split by tree into 152 for training and 49 for testing.
2. **Eight generators** covering the three families in the literature:

   | Family | Generators |
   |---|---|
   | Learn from real trees | **G0** radius noise · **G1** allometric perturbation · **G2** same-species branch recombination · **G3** hybrid · **G4** procedural, sampling rules from real branches |
   | Botanical rules | **G5** allometry, phyllotaxis, mean taper profiles |
   | Growth algorithm | **G6** *space colonization* |

3. **Evaluation against held-out real trees**, always reported next to the real–real reference:
   - fidelity: normalized Wasserstein distance on 22 tree traits and 10 branch traits, plus a 1-NNA test;
   - novelty: is it a new tree or a copy?;
   - botanical validity.
4. **Virtual forest in Isaac Sim 6.2**, built with the best mix (G2 + G4) and with branches modelled as continuous tubes. There are two versions with the same trees and the same route:
   - **v1:** trees only;
   - **v2:** dressed forest, with terrain, understory, deadwood, rocks and an outer ring of trees.

   A platform carries a **128-channel Ouster OS1 LiDAR** and an **RGB-D camera** (RealSense D455 optics). The data are labelled per class at 10 Hz and shown **in real time** with Rerun.

### Main results

| | Real (ref.) | G0 | G1 α=0.25 | G2 | G3 | G4 | G5 | G6 | **G2+G4** |
|---|---|---|---|---|---|---|---|---|---|
| 1-NNA (50 % = indistinguishable) | 45.5 % | 54.2 % | 57.0 % | 55.9 % | 55.9 % | 63.2 % | 89.2 % | 97.8 % | **54.6 %** |
| Novelty (0 = copy, 1 = a different tree) | 1.00 | 0.31 | 0.38 | 0.73 | 0.81 | 1.60 | 1.98 | 2.13 | **1.19** |

**How to read it:**
- Recombination (G2) is the most faithful.
- G4 is the only realistic generator that creates genuinely new trees.
- Their mix, G2+G4, keeps the fidelity of G2 and nearly doubles the novelty.
- The generators that use no real data (G5, G6) are easy to tell apart from real trees.

In Isaac, the dressing of v2 changes what the sensors see a lot: understory becomes **21.7 %** of the LiDAR points, a class that does not exist in v1.

<p align="center"><img src="paper/figs/generadores.png" width="100%"><br><em>A real tree (left) and one synthetic tree from each generator.</em></p>
<p align="center"><img src="paper/figs/sensores_v1_v2.png" width="100%"><br><em>RGB-D camera at the same pose in v1 and v2: RGB, depth and segmentation.</em></p>

---

## Repository layout

```
Synthetic_Tree_G/
├── scripts/                    Full pipeline, in order (01 → 05)
│   ├── 01_download_data.sh     Downloads the 201 QSMs from Zenodo (37 MB, MD5-checked)
│   ├── 02_run_synth_trees.sh   Part 1: traits, generators G0–G6, evaluation, tables and figures
│   ├── 03_build_scenes.sh      Part 2: Poly Haven assets + Isaac Sim scenes v1 and v2
│   ├── 04_record_sensors.sh    Part 3: sensor recordings, screenshots, v1/v2 comparison, videos
│   └── 05_build_paper.sh       Builds the paper
├── synth_trees/                Part 1: synthetic trees (pure Python)
│   ├── qsm.py                  TreeQSM reader, topology, local (turtle-style) encoding
│   ├── traits.py               Tree and branch traits (same code for real and synthetic trees)
│   ├── generators.py           G0–G6
│   ├── run_extract.py          Cleaning, cache, real-tree traits and train/test split
│   ├── run_generate.py         Generates 5 synthetic trees per training tree with one generator
│   ├── evaluate.py             W1n, 1-NNA, novelty and validity against the test trees
│   ├── evaluate_mixtures.py    Generator mixes (5 seeds)
│   ├── data_stats.py           Data descriptives, TreeQSM gaps, Leonardo exponent
│   ├── make_figures.py         Figures for part 1 of the paper
│   └── render.py               Side view of a real tree and its synthetic versions
├── isaac_forest/               Parts 2 and 3: virtual forest and sensors (Isaac Sim 6.2)
│   ├── meshing.py              QSM → mesh of one continuous tube per branch
│   ├── dressing.py             Terrain, route, understory, deadwood, rocks
│   ├── build_forest.py         Builds the USD scene (v1 with --bare, v2 by default)
│   ├── run_sensors.py          Platform with OS1 LiDAR + RGB-D camera; records labelled frames
│   ├── viewer.py               Real-time viewer / player (Rerun)
│   ├── demo.sh                 Demo launcher (Isaac + live viewer)
│   └── tools/                  Assets, screenshots, v1/v2 comparison, videos, sensor test
├── paper/                      Paper (LaTeX, Spanish): main.tex, refs.bib, figs/, main.pdf
├── docs/                       (Spanish)
│   ├── RESULTADOS_ESPERADOS.md Reference numbers to check a replication
│   ├── DATOS.md                Sensor data format and classes
│   └── DATOS_EXTERNOS.md       What is on Google Drive and where to put it
├── requirements.txt            Dependencies for part 1 and the analysis tools
├── requirements-viewer.txt     Viewer dependencies (separate environment)
├── CITATION.cff
└── LICENSE                     MIT (code). Third-party data and assets: see Licenses
```

What the pipeline generates (`data/`, `synth_trees/work/`, `isaac_forest/{assets,scenes,recordings,screenshots,videos}/`) is not version-controlled. You can regenerate it with `scripts/` or download it from Drive.

---

## Requirements

| Part | Requirements |
|---|---|
| 1. Synthetic trees | Python 3.12, `requirements.txt`. Multi-core CPU (runs in parallel). No GPU needed |
| 2–3. Isaac Sim | NVIDIA RTX GPU (tested: RTX 5070 Ti 16 GB, driver 595), Ubuntu 22.04/24.04, **Isaac Sim 6.2.0** (pip), ~25 GB of disk for Isaac |
| Viewer | `requirements-viewer.txt`, in an environment **separate** from Isaac's. Installing it into the Isaac environment would change Isaac's pinned `psutil` version |
| Videos | `ffmpeg` |
| Paper | TeX Live with `biber`, `biblatex`, `babel-spanish` |

Test environment: Ubuntu 24.04.5, Python 3.12.3, Isaac Sim 6.2.0.0, PyTorch 2.11 (CUDA 13), NVIDIA driver 595.91.

### Installation

```bash
git clone https://github.com/Nosl3n/Synthetic_Tree_G.git
cd Synthetic_Tree_G

# Part 1 and analysis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Isaac Sim 6.2 (its own environment; official instructions: https://docs.isaacsim.omniverse.nvidia.com)
python3.12 -m venv ~/isaacsim_env
~/isaacsim_env/bin/pip install "isaacsim[all,extscache]==6.2.0.0" --extra-index-url https://pypi.nvidia.com
~/isaacsim_env/bin/pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu130   # as in the tested environment
export ISAAC_PY=~/isaacsim_env/bin/python
export OMNI_KIT_ACCEPT_EULA=YES          # accepts the NVIDIA Omniverse licence

# Viewer (separate environment)
python3 -m venv isaac_forest/.venv_viz
isaac_forest/.venv_viz/bin/pip install -r requirements-viewer.txt
```

---

## Reproducing everything

With `.venv` activated and `ISAAC_PY` set:

```bash
bash scripts/01_download_data.sh     # ~20 s
bash scripts/02_run_synth_trees.sh   # ~3 min with 32 cores (longer with fewer)
bash scripts/03_build_scenes.sh      # ~1 min (includes ~450 MB of Poly Haven assets)
bash scripts/04_record_sensors.sh    # ~8 min (RTX 5070 Ti)
bash scripts/05_build_paper.sh       # ~1 min
```

- **Determinism:** all random seeds are fixed. The train/test split, the 6,080 synthetic trees, the metrics, the scenes and the platform route are reproduced exactly.
- **Reference values:** [`docs/RESULTADOS_ESPERADOS.md`](docs/RESULTADOS_ESPERADOS.md) lists the numbers to compare your run against.
- **Verified:** a from-scratch run in a clean environment reproduces the synthetic trees and all metrics bit for bit, and builds identical scenes. The camera is deterministic; the RTX LiDAR varies by less than 0.01 % between runs because of the order of GPU operations. Speed depends on the hardware.

**Part 1 only**, without a GPU: run `01` and `02`. This produces all the generator tables in the paper.

---

## Real-time demo

```bash
cd isaac_forest
./demo.sh                              # v2: headless Isaac + live Rerun viewer
WORLD=forest_v1_arboles ./demo.sh      # v1: trees only
./demo.sh gui                          # also opens the Isaac window, with the LiDAR cloud drawn
./demo.sh web                          # viewer in the browser
./demo.sh replay                       # no Isaac: replays recordings/v2_bosque (or download it from Drive)
```

The viewer shows:
- **3D:** the current LiDAR scan by class, the accumulated map, the ground-truth tree skeletons, the trajectory, and the camera with its depth projected;
- **2D:** RGB, depth and segmentation;
- **time series:** points per class.

---

## External data (Google Drive)

Large files are not in the repository. They are on Google Drive:

**🔗 [Google Drive folder](https://drive.google.com/drive/folders/1A_rpW5E1f6_VL9n4JmHMmiPmwXZPpeNK?usp=sharing)**

| Folder | Contents | Approx. size | How to regenerate |
|---|---|---|---|
| `01_datos_sensores/` | v1 and v2 recordings (840 labelled frames each) | 1.8 + 2.7 GB | `04_record_sensors.sh` |
| `02_rerun/` | The same recordings in Rerun format (`.rrd`), viewable without Isaac (like a *rosbag*) | 1.6 + 2.8 GB | `viewer.py --replay --save` |
| `03_videos/` | Sample video of each route | 47 + 157 MB | `tools/make_video.py` |
| `04_escenas/` | v1 and v2 USD scenes, ready to open in Isaac Sim | 0.17 GB (+ Poly Haven assets) | `03_build_scenes.sh` |
| `05_arboles_sinteticos/` | Processed real trees and the 8 synthetic sets, with traits and evaluations | 0.6 GB | `02_run_synth_trees.sh` |
| `06_capturas/` | Simulator screenshots | 39 MB | `tools/screenshots.py` |

[`docs/DATOS_EXTERNOS.md`](docs/DATOS_EXTERNOS.md) (Spanish) explains where to put each folder so the code can use it, for example to view the recordings or open the scenes without regenerating them.

---

## How to cite

```bibtex
@misc{synthetic_tree_g_2026,
  author = {Broyer-Paco, Nelson and Marquez-Aguilar, Angel and Shi, Li and Josine and Pacifique},
  title  = {Synthetic\_Tree\_G: Generating synthetic tropical trees from real QSM tree models,
            with a virtual forest for LiDAR and depth-camera simulation in Isaac Sim},
  year   = {2026},
  url    = {https://github.com/Nosl3n/Synthetic_Tree_G}
}
```

Please also cite the data: Krishna Moorthy, S. M. et al. (2022). *Datasets to quantify the impact of lianas on 3D tree structure and biomass*. Zenodo. https://doi.org/10.5281/zenodo.6981485

## Licenses

- **Code:** MIT ([LICENSE](LICENSE)).
- **BCI QSMs:** CC BY 4.0 (Krishna Moorthy et al. 2022). They are downloaded, not redistributed.
- **Textures, HDRI skies and 3D models:** [Poly Haven](https://polyhaven.com), CC0. Downloaded with `tools/download_assets.py`.
- **Isaac Sim:** NVIDIA Omniverse licence (using it means accepting its EULA).

## Known limitations

- **Traits are measured on QSMs**, which are reconstructions with their own biases. 4.7 % of TreeQSM joints have gaps larger than 20 cm. Synthetic trees that copy real geometry inherit them; the Isaac meshes close them.
- **With 49 test trees**, 1-NNA has low statistical power.
- **The forest seen in the background of the camera in v2** is the HDRI sky photo: it has no depth, it is labelled as background, and the LiDAR does not see it.
- **The camera depth is ideal** (no stereo noise), and the trees have no leaves.
- **Still to do:** measure how useful the synthetic data are for training networks (TSTR).

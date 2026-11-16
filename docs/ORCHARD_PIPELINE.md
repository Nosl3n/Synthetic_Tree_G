# Orchard pipeline — QSM variation and the apple-orchard transfer

The orchard pipeline is the "transfer to orchard" extension of Synthetic_Tree_G. It reuses the
same cylinder-table machinery as the tropical trees (`synth_trees/qsm.py`) to do two things:

1. **Perturb TreeQSM models** at the cylinder-table level and measure the effect on the
   aggregate tree metrics (volume, area, length, DBH) — a robustness / augmentation study.
2. **Bring apple/orchard trees into the same representation**, so a pruned Bibaum apple tree
   can be compared directly with the tropical trees.

This is the work behind the "transfer to orchard" argument in the English deck and abstract:
the same cylinder representation and generators transfer to agricultural trees.

## Data flow

```
mat/MultipleQSMModels/*.mat          input TreeQSM models (gitignored); without it the scripts
                                     use data/bci_zenodo_6981485/QSMs/ (scripts/01_download_data.sh)
   │  vary_qsm.py  (radius | length | axis)
   ├─> <out>/summary.csv             per-variant metric delta (one row per seed × model)
   ├─> <out>/cylinders/*.csv         per-cylinder tables of the varied QSMs
   └─> <out>/mat/*__<variant>.mat    varied QSMs (skip with --no-mat)
   │  export_parquet.py
   └─> qsms.parquet                  one row per cylinder, originals + varied (zstd)
   │  visualize.py / render_solid.py
   └─> viz/*.png                     skeleton / solid-shaded renders
```

### Input models

The results below were computed on `mat/MultipleQSMModels/`: a TreeQSM parameter ensemble run on the
wood point clouds of the BCI dataset (Krishna Moorthy et al. 2022, Zenodo 6981485, CC BY 4.0), about
10 models per tree, 2,008 in all. Its files are named
`<cloud>-<PatchDiam1>-<PatchDiam2Min>-<PatchDiam2Max>-<model>`. The published dataset keeps one model
per tree, with patch settings chosen per tree (TreeQSM 2.4.0; for `ALBLAC_1082`, `0.12-0.04-0.1`, model
1). The ensemble is not distributed with this repository. Without it, every script falls back to the 201
published models that `scripts/01_download_data.sh` downloads, and `vary_qsm.py`, `export_parquet.py` and
`visualize.py` read both file layouts, so the whole pipeline runs from a fresh clone; the numbers then
cover one model per tree instead of the ensemble.

## Scripts

| Script | What it does |
|---|---|
| `vary_qsm.py` | Perturbs a TreeQSM cylinder table — `--mode radius` (scale radii by `--frac`), `length` (scale lengths), or `axis` (rotate axes by `--axis-deg` degrees) — recomputes volume/area/length/DBH, and writes new `.mat`, per-cylinder CSVs and `summary.csv`. Topology (parent/extension/branch/order) is left untouched. |
| `export_parquet.py` | Flattens original + varied `.mat` files into one `qsms.parquet` (one row per cylinder; radius/length/coords in m, volume in litres). |
| `visualize.py` | Renders QSM skeletons as PNG — one line segment per cylinder, coloured by branch order, linewidth ∝ radius. |
| `render_solid.py` | Renders a single QSM as solid, shaded cylinders (Lambert shading, viridis by branch order) to `viz/<tree>_solid.png`. |
| `make_apple_comparison.py` | Builds a procedural open-centre (vase) apple tree, saves `apple/apple_procedural.npz`, and renders it beside the first tropical QSM → `apple/apple_vs_tropical.png`. |
| `taper_profiles.py` | Extracts the full trunk taper profile (radius vs relative height, normalised by r(1.3 m)) for every QSM → `taper/taper_profiles.csv` and a per-species mean → `taper/taper_summary.csv`. |
| `fit_taper.py` | Bayesian hierarchical trunk-taper fit — `log radius = α + u_tree + β·x` with an exact Gibbs sampler — then samples new taper curves → `taper/taper_<species>.csv` + PNG. |
| `borrow_apple_qsm.py` | Converts the real Bibaum apple QSM (GroIMP `.qsm` CSV, read from `BIBAUM_QSM_DIR`) into the `Tree` format and renders real / procedural / tropical → `apple/bibaum_*.npz`, `apple_real_vs_tropical.png`, `apple_vs_tropical_deck.png`. |

## Running

```bash
# 1. Radius perturbation ±10%, 3 seeds, across all QSMs
python vary_qsm.py --input mat/MultipleQSMModels --output varied_radius --mode radius --frac 0.1 --seeds 0 1 2

# 2. Length perturbation ±5%, 3 seeds, across all QSMs
python vary_qsm.py --input mat/MultipleQSMModels --output length --mode length --frac 0.05 --seeds 0 1 2

# 3. Axis rotation (degrees) — demo/control, 1 file (metrics are orientation-invariant)
python vary_qsm.py --input mat/MultipleQSMModels --output demo_length_axis --mode axis --axis-deg 3.0 --seeds 0 --limit 1

# 4. Consolidate to Parquet
python export_parquet.py --dirs mat/MultipleQSMModels varied_radius/mat length/mat --out qsms.parquet

# 5. Visualise
python visualize.py mat/MultipleQSMModels/*.mat --outdir viz
python render_solid.py          # one solid render -> viz/<tree>_solid.png

# 6. Apple comparison
python make_apple_comparison.py

# 7. Taper profiles
python taper_profiles.py
```

## What `summary.csv` measures

`vary_qsm.py` recomputes only the aggregate metrics that follow from the cylinder table:
tree volume (litres), area (m²), length (m) and DBH. The complex `treedata` distributions
(StemTaper, VerticalProfile, volume/diameter histograms) are **not** recomputed — they stay
those of the source model. Columns: `qsm_id, tree, model, variant, seed, mode, frac,
n_cylinders, vol_before_L, vol_after_L, vol_pct_change, area_before_m2, area_after_m2,
length_before_m, length_after_m`.

## Results so far

- **Radius variation (`varied_radius/`)** — complete. ±10% radius (frac 0.1), 3 seeds, many
  trees/models. Volume responds near-linearly with the radius change: +10% radius gives roughly
  +1–2% volume (e.g. ALBLAC_1082 model 1: +1.41 / +1.21 / −0.84% for seeds 0/1/2); area moves
  with it; length is unchanged (topology preserved).
- **Length variation (`length/`)** — complete. ±5% per-cylinder length (frac 0.05), 3 seeds,
  201 trees. The per-cylinder perturbations average out over ~1 000 cylinders, so aggregate
  length/volume/area move only ~±0.5% (mean ≈ 0): length −0.50…+0.56%, volume −0.89…+0.83%,
  area −0.41…+0.58%.
- **Axis variation (`demo_length_axis/`)** — control only (1 tree, 1 seed, 3°). Volume/area/length
  are unchanged (0.0%), as expected: rotating an axis does not change cylinder dimensions — it
  confirms the metric recompute is orientation-invariant.
- **Taper (`taper/`)** — complete. `taper_profiles.py` extracts the full trunk taper profile
  (radius vs relative height, normalised by r(1.3 m)) for all 2 008 QSMs
  (`taper_profiles.csv`, 146 827 rows) and a per-species mean at the 9 paper heights
  (`taper_summary.csv`, 53 species). Most species taper smoothly (normalised radius ~1.0 at the
  base → ~0.25 at 0.9 relative height). The `taper_ALBLAC.csv` / `.png` (27 ALBLAC trees,
  `x` = relative height, `y` = log radius) come from `fit_taper.py`, the Bayesian hierarchical
  fit.
- **Apple transfer (`apple/`)** — procedural open-centre apple tree (`apple_procedural.npz`)
  beside a tropical QSM (`apple_vs_tropical.png`); real Bibaum apple QSMs
  (`bibaum_prepruned.npz`, `bibaum_pruned.npz`; provenance and CC BY 4.0 licence in `apple/README.md`) and
  `apple_real_vs_tropical.png` for the real-orchard comparison; `apple_vs_tropical_deck.png` is
  the deck figure. The Bibaum `.npz` files are produced by `borrow_apple_qsm.py` and consumed by `build_pptx.py`.

## Current state (2026-11-13)

- Complete: radius + length variation runs, taper profiles (all 53 species), apple transfer
  (procedural + real), solid render, Parquet export.
- Axis variation is kept as a single-sample control (its metric summary is trivially zero).
- Regenerable outputs (`mat/`, `qsms.parquet`, `varied_radius/`, `length/`, `demo_length_axis/`,
  `taper/`, `viz/`) are gitignored and regenerate from the scripts above.

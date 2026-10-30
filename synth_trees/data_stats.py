"""Descriptivos del conjunto real (tabla 1 del paper) y comprobaciones de los QSM.

    python3 data_stats.py            # después de run_extract.py
Salida: work/data_stats.json
  - n.º de árboles y especies, altura, cilindros, ramas, orden máximo, radio de cilindro
  - fracción de cilindros descartados por no estar conectados al cilindro 0
  - huecos de TreeQSM: uniones entre cilindros consecutivos separadas más de 20 cm
  - exponente de Leonardo Δ (mediana por bifurcación, árboles de train)
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd
import scipy.io as sio

import generators as G
import qsm


def raw_count(path):
    d = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    c = d['QSM'].cylinder if 'QSM' in d else d['cylinder']
    return len(np.atleast_1d(c.radius))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--qsm-dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data',
                                                      'bci_zenodo_6981485', 'QSMs'))
    ap.add_argument('--gap', type=float, default=0.20)
    args = ap.parse_args()
    trees = pd.read_csv(os.path.join(args.work, 'real_trees.csv'))
    split = pd.read_csv(os.path.join(args.work, 'split.csv'))
    radii, gaps_frac, trees_with_gap, dropped, n_joints, n_gaps = [], [], 0, [], 0, 0
    for name in trees.tree:
        t = qsm.load_npz(os.path.join(args.work, 'real', name + '.npz'))
        radii.append(t.radius)
        i = np.where(t.ext >= 0)[0]
        g = np.linalg.norm(t.end[i] - t.start[t.ext[i]], axis=1)
        n_joints += len(g)
        n_gaps += int((g > args.gap).sum())
        trees_with_gap += int((g > args.gap).any())
        mats = glob.glob(os.path.join(args.qsm_dir, name + '.mat'))
        if mats:
            dropped.append(1 - t.n / raw_count(mats[0]))
    r = np.concatenate(radii)
    q = lambda x: [float(np.percentile(x, 25)), float(np.median(x)), float(np.percentile(x, 75))]
    train = [qsm.load_npz(os.path.join(args.work, 'real', n + '.npz')) for n in split[split.split == 'train'].tree]
    out = dict(
        n_trees=int(len(trees)), n_species=int(trees.species.nunique()),
        n_train=int((split.split == 'train').sum()), n_test=int((split.split == 'test').sum()),
        height_mean_sd=[float(trees.height.mean()), float(trees.height.std())],
        n_cyl_q25_med_q75=q(trees.n_cyl), n_branches_q25_med_q75=q(trees.n_branches),
        max_order_median_min_max=[float(trees.max_order.median()), int(trees.max_order.min()), int(trees.max_order.max())],
        cyl_radius_cm_q25_med_q75=[100 * v for v in q(r)],
        dropped_cylinders_mean_pct=float(100 * np.mean(dropped)) if dropped else None,
        qsm_gaps=dict(threshold_m=args.gap, pct_joints=100 * n_gaps / n_joints, trees_with_gaps=trees_with_gap),
        leonardo_delta_train=G.pipe_exponent(train),
    )
    json.dump(out, open(os.path.join(args.work, 'data_stats.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()

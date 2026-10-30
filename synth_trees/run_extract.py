"""Paso 1: cargar los 201 QSM, cachearlos, medir rasgos y fijar el split por árbol.

Salidas en work/:
  real/<arbol>.npz       árbol limpio (solo la parte conectada a la raíz)
  real_trees.csv         rasgos por árbol
  real_branches.csv      rasgos por rama
  split.csv              tree, species, split (train/test), estratificado por especie
"""
import argparse
import glob
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import qsm
import traits


def process(path, outdir):
    t = qsm.load_mat(path)
    qsm.save_npz(t, os.path.join(outdir, 'real', t.name + '.npz'))
    tt = traits.tree_traits(t)
    tt.update(tree=t.name, species=t.species)
    bt = traits.branch_table(t)
    bt['tree'], bt['species'] = t.name, t.species
    return tt, bt


def make_split(names, species, test_frac, seed):
    """Por especie: ~test_frac de los árboles a test; especies con 1 árbol van a train."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(dict(tree=names, species=species, split='train'))
    for sp, g in df.groupby('species'):
        k = int(round(len(g) * test_frac)) if len(g) >= 3 else 0
        df.loc[rng.choice(g.index, k, replace=False), 'split'] = 'test'
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--qsm-dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'bci_zenodo_6981485', 'QSMs'))
    ap.add_argument('--out', default='work')
    ap.add_argument('--test-frac', type=float, default=0.3)
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, 'real'), exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.qsm_dir, '*.mat')))
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(process, files, [args.out] * len(files)))
    trees = pd.DataFrame([r[0] for r in res])
    branches = pd.concat([r[1] for r in res], ignore_index=True)
    split = make_split(trees.tree, trees.species, args.test_frac, args.seed)
    trees = trees.merge(split[['tree', 'split']], on='tree')
    branches = branches.merge(split[['tree', 'split']], on='tree')
    trees.to_csv(os.path.join(args.out, 'real_trees.csv'), index=False)
    branches.to_csv(os.path.join(args.out, 'real_branches.csv'), index=False)
    split.to_csv(os.path.join(args.out, 'split.csv'), index=False)
    print(f'{len(trees)} árboles, {len(branches)} ramas, '
          f'{(split.split == "train").sum()} train / {(split.split == "test").sum()} test')


if __name__ == '__main__':
    main()

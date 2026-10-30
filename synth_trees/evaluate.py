"""Paso 3: ¿qué tan parecidos son los sintéticos a los árboles reales?

Compara cada generador con los árboles reales de TEST (nunca usados para generar
ni para ajustar estadísticos) y reporta cada métrica junto a su referencia
real-real (train vs test). Un sintético es "tan real como lo real" si su
distancia a test es similar a la de train a test.

Métricas
  W1n      Wasserstein-1 / desviación típica real, por rasgo (árbol y rama).
  1-NNA    precisión de un 1-NN que distingue sintético de real-test sobre el
           vector de rasgos estandarizado. 50 % = indistinguibles.
  copia    distancia de cada sintético a su árbol fuente / distancia típica al
           vecino real más cercano. ~0 = copia, ~1 = tan distinto como otro árbol.
  validez  % de ramas más gruesas que su padre, regla de tubería.
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance

TREE_TRAITS = ['height', 'dbh', 'vol_total', 'branch_vol_frac', 'len_total', 'n_branches',
               'max_order', 'n_br_o1', 'n_br_o2', 'crown_area', 'crown_diam', 'crown_base_rel',
               'o1_angle_med', 'o1_diam_ratio_med', 'o1_child_density', 'pipe_med',
               'vol_frac_o1', 'vol_frac_o2', 'taper_03', 'taper_05', 'taper_07', 'taper_09']
LOG_TRAITS = {'height', 'dbh', 'vol_total', 'len_total', 'crown_area', 'crown_diam'}
COUNT_TRAITS = {'n_branches', 'n_br_o1', 'n_br_o2'}      # log(1+x): pueden valer 0
BRANCH_TRAITS = ['insert_angle', 'diam_ratio', 'length_ratio', 'zenith', 'child_density']


def _tx(df, cols):
    X = df[cols].astype(float).copy()
    for c in cols:
        if c in LOG_TRAITS:
            X[c] = np.log(X[c].clip(1e-6))
        elif c in COUNT_TRAITS:
            X[c] = np.log1p(X[c])
    return X


def w1n(a, b, scale):
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    return wasserstein_distance(a, b) / scale if len(a) and len(b) else np.nan


def one_nna(A, B):
    """Precisión 1-NN leave-one-out entre los conjuntos A y B (mismo tamaño)."""
    X = np.vstack([A, B])
    y = np.r_[np.zeros(len(A)), np.ones(len(B))]
    D = np.linalg.norm(X[:, None] - X[None], axis=-1)
    np.fill_diagonal(D, np.inf)
    return np.mean(y[D.argmin(1)] == y)


def evaluate(real, real_br, syn, syn_br, rng, reps=50):
    test, train = real[real.split == 'test'], real[real.split == 'train']
    allr = _tx(real, TREE_TRAITS)
    mu, sd = allr.mean(), allr.std()
    Z = lambda df: ((_tx(df, TREE_TRAITS) - mu) / sd).fillna(0).values
    Zte, Ztr, Zsy = Z(test), Z(train), Z(syn)
    out = {}
    for c in TREE_TRAITS:
        out[f'W1n:{c}'] = w1n(_tx(syn, [c])[c].values, _tx(test, [c])[c].values, allr[c].std())
    br_te = real_br[real_br.split == 'test']
    for c in BRANCH_TRAITS:
        s = real_br[c].std()
        for o in (1, 2):
            out[f'W1n:br_o{o}_{c}'] = w1n(syn_br[syn_br.order == o][c].values,
                                          br_te[br_te.order == o][c].values, s)
    n = len(Zte)
    out['1NNA'] = np.mean([one_nna(Zte, Zsy[rng.choice(len(Zsy), n, replace=False)]) for _ in range(reps)])
    # copia: distancia a su fuente vs distancia al vecino real más cercano entre árboles de train
    Dtr = np.linalg.norm(Ztr[:, None] - Ztr[None], axis=-1)
    np.fill_diagonal(Dtr, np.inf)
    nn_real = np.median(Dtr.min(1))
    if 'source' in syn:
        pos = {n: i for i, n in enumerate(train.tree)}
        src = Ztr[[pos[s] for s in syn.source]]
        out['copia'] = np.median(np.linalg.norm(Zsy - src, axis=1)) / nn_real
    out['ramas>padre_%'] = 100 * np.mean(syn_br.diam_ratio > 1.0)
    out['pipe_med'] = syn.pipe_med.median()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    real = pd.read_csv(os.path.join(args.work, 'real_trees.csv'))
    real_br = pd.read_csv(os.path.join(args.work, 'real_branches.csv'))
    rows = {}
    tr = real[real.split == 'train']
    trb = real_br[real_br.split == 'train']
    rows['REAL train (ref.)'] = evaluate(real, real_br, tr, trb, rng)
    rows['REAL train (ref.)']['copia'] = 1.0
    for d in sorted(glob.glob(os.path.join(args.work, 'syn_*'))):
        syn = pd.read_csv(os.path.join(d, 'trees.csv'))
        syn_br = pd.read_csv(os.path.join(d, 'branches.csv'))
        rows[os.path.basename(d)[4:]] = evaluate(real, real_br, syn, syn_br, rng)
    res = pd.DataFrame(rows)
    w = res.index.str.startswith('W1n:')
    summary = pd.concat([res[~w], pd.DataFrame(
        {'W1n árbol (media)': res[w & ~res.index.str.contains(':br_')].mean(),
         'W1n rama (media)': res[res.index.str.contains(':br_')].mean()}).T])
    res.to_csv(os.path.join(args.work, 'eval_full.csv'))
    summary.to_csv(os.path.join(args.work, 'eval_summary.csv'))
    pd.set_option('display.width', 250)
    print(summary.round(3).to_string())
    print()
    print(res[w].round(3).to_string())


if __name__ == '__main__':
    main()

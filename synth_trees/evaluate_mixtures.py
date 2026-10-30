"""Mezclas de generadores (tabla de combinaciones del paper).

Cada mezcla tiene 760 árboles en total, a partes iguales de cada generador, y se
evalúa con 5 semillas (submuestreo distinto en cada una) frente a los árboles de test.

    python3 evaluate_mixtures.py     # después de evaluate.py
Salida: work/eval_mixtures.csv (media y d.e. por mezcla)
"""
import argparse
import os

import numpy as np
import pandas as pd

import evaluate as E

MIXES = {
    'REAL train (ref.)': None,
    'G2': ['recombine'],
    'G4': ['procedural'],
    'G2+G4': ['recombine', 'procedural'],
    'G2+G3+G4': ['recombine', 'hybrid', 'procedural'],
    'G2+G5': ['recombine', 'rules'],
    'G2+G6': ['recombine', 'colonization'],
}
N_TOTAL = 760


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--seeds', type=int, default=5)
    args = ap.parse_args()
    real = pd.read_csv(os.path.join(args.work, 'real_trees.csv'))
    rb = pd.read_csv(os.path.join(args.work, 'real_branches.csv'))
    cache = {}

    def load(g):
        if g not in cache:
            d = os.path.join(args.work, 'syn_' + g)
            cache[g] = (pd.read_csv(os.path.join(d, 'trees.csv')), pd.read_csv(os.path.join(d, 'branches.csv')))
        return cache[g]

    rows = []
    for name, gs in MIXES.items():
        for seed in range(args.seeds):
            rng = np.random.default_rng(100 + seed)
            if gs is None:
                T, B = real[real.split == 'train'], rb[rb.split == 'train']
            else:
                T = pd.concat([load(g)[0].sample(N_TOTAL // len(gs), random_state=seed) for g in gs], ignore_index=True)
                B = pd.concat([load(g)[1] for g in gs], ignore_index=True)
                B = B[B.tree.isin(T.tree)]
            r = pd.Series(E.evaluate(real, rb, T, B, rng))
            w = r.index.str.startswith('W1n:')
            rows.append(dict(mezcla=name, seed=seed, NNA=r['1NNA'], copia=r.get('copia', 1.0),
                             W1n_arbol=r[w & ~r.index.str.contains(':br_')].mean(),
                             W1n_rama=r[r.index.str.contains(':br_')].mean()))
    df = pd.DataFrame(rows)
    df.loc[df.mezcla == 'REAL train (ref.)', 'copia'] = 1.0
    summ = df.groupby('mezcla', sort=False).agg(['mean', 'std']).drop(columns='seed')
    summ.columns = ['_'.join(c) for c in summ.columns]
    summ.to_csv(os.path.join(args.work, 'eval_mixtures.csv'))
    print(summ.round(3).to_string())


if __name__ == '__main__':
    main()

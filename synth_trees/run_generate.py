"""Paso 2: generar árboles sintéticos a partir de los árboles de train.

Salidas en work/syn_<generador>/:
  <arbol>__<gen>_s<k>.npz   árbol sintético
  trees.csv                 rasgos por árbol (mismo código que los reales) + metadatos
  branches.csv              rasgos por rama
"""
import argparse
import json
import os
import zlib
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import generators as G
import qsm
import traits

_STATE = {}


def _init(work, gen, params, out=None):
    trees = pd.read_csv(os.path.join(work, 'real_trees.csv'))
    branches = pd.read_csv(os.path.join(work, 'real_branches.csv'))
    _STATE.update(work=work, gen=gen, params=params, out=out, st=G.fit_stats(trees, branches))
    train = trees[trees.split == 'train'].tree
    if gen in ('recombine', 'hybrid'):
        _STATE['pool'] = G.DonorPool([qsm.load_npz(os.path.join(work, 'real', n + '.npz')) for n in train])
    if gen in ('procedural', 'rules', 'colonization'):
        tl = [qsm.load_npz(os.path.join(work, 'real', n + '.npz')) for n in train]
        _STATE['rules'] = G.ProcRules(tl)
        if gen != 'procedural':
            _STATE['ruleset'] = G.RuleSet(tl, trees, _STATE['rules'])
            _STATE['traits'] = trees.set_index('tree').to_dict('index')


def _job(args):
    name, k = args
    S = _STATE
    t = qsm.load_npz(os.path.join(S['work'], 'real', name + '.npz'))
    rng = np.random.default_rng(zlib.crc32(f'{S["gen"]}/{name}/{k}'.encode()))
    if S['gen'] == 'iid_radius':
        s = G.iid_radius(t, rng, **S['params'])
    elif S['gen'] == 'allometric':
        s = G.allometric(t, rng, S['st'], **S['params'])
    elif S['gen'] == 'recombine':
        s = G.recombine(t, rng, S['pool'], S['st'], **S['params'])
    elif S['gen'] == 'hybrid':
        s = G.hybrid(t, rng, S['pool'], S['st'], **S['params'])
    elif S['gen'] == 'procedural':
        s = G.procedural(t, rng, S['rules'], S['st'], **S['params'])
    elif S['gen'] == 'rules':
        s = G.rule_based(t, rng, S['ruleset'], S['st'], **S['params'])
    else:
        t.meta['traits'] = S['traits'][name]
        s = G.space_colonization(t, rng, S['ruleset'], S['st'], **S['params'])
    sid = f'{name}__{os.path.basename(S["out"])[4:]}_s{k}'
    s.name = sid
    qsm.save_npz(s, os.path.join(S['out'], sid + '.npz'))
    tt = traits.tree_traits(s)
    tt.update(tree=sid, species=t.species, source=name, generator=os.path.basename(S['out'])[4:], seed=k,
              meta=json.dumps(s.meta))
    bt = traits.branch_table(s)
    bt['tree'], bt['species'] = sid, t.species
    return tt, bt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', required=True, choices=['iid_radius', 'allometric', 'recombine', 'hybrid', 'procedural', 'rules', 'colonization'])
    ap.add_argument('--work', default='work')
    ap.add_argument('--n', type=int, default=5, help='sintéticos por árbol de train')
    ap.add_argument('--params', default='{}', help='JSON con parámetros del generador')
    ap.add_argument('--tag', default='', help='sufijo de la carpeta de salida')
    args = ap.parse_args()
    params = json.loads(args.params)
    out = os.path.join(args.work, 'syn_' + args.gen + (f'_{args.tag}' if args.tag else ''))
    os.makedirs(out, exist_ok=True)
    split = pd.read_csv(os.path.join(args.work, 'split.csv'))
    jobs = [(n, k) for n in split[split.split == 'train'].tree for k in range(args.n)]
    with ProcessPoolExecutor(initializer=_init, initargs=(args.work, args.gen, params, out)) as ex:
        res = list(ex.map(_job, jobs, chunksize=4))
    _init(args.work, 'iid_radius', {})   # solo para mostrar los estadísticos ajustados
    pd.DataFrame([r[0] for r in res]).to_csv(os.path.join(out, 'trees.csv'), index=False)
    pd.concat([r[1] for r in res], ignore_index=True).to_csv(os.path.join(out, 'branches.csv'), index=False)
    st = _STATE['st']
    print(f'{args.gen}: {len(res)} árboles -> {out}')
    print('estadísticos (train):', {k: (round(v, 3) if np.isscalar(v) else {o: round(x, 3) for o, x in v.items()})
                                    for k, v in st.items()})


if __name__ == '__main__':
    main()

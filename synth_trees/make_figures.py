"""Figuras de la parte de generadores del paper (paper/figs/).

    python3 make_figures.py          # después de evaluate.py y evaluate_mixtures.py
  fidelidad_novedad.pdf   1-NNA frente a novedad de cada generador y de la mezcla G2+G4
  w1_rasgos.pdf           W1 normalizada por rasgo de árbol
  generadores.png         un árbol real y un sintético de cada generador
"""
import argparse
import os
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {'REAL train (ref.)': 'Real (ref.)', 'iid_radius': 'G0', 'allometric_a025': 'G1 α=0,25',
         'allometric_a050': 'G1 α=0,5', 'recombine': 'G2', 'hybrid': 'G3', 'procedural': 'G4',
         'rules': 'G5', 'colonization': 'G6'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='work')
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'paper', 'figs'))
    ap.add_argument('--tree', default='TRITUB_213134')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    e = pd.read_csv(os.path.join(args.work, 'eval_summary.csv'), index_col=0)
    mix = pd.read_csv(os.path.join(args.work, 'eval_mixtures.csv'), index_col=0)

    # fidelidad frente a novedad
    grp = {'Real (ref.)': 'k', 'G5': 'tab:orange', 'G6': 'tab:red'}
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for k, n in NAMES.items():
        x, y = e.loc['copia', k], 100 * e.loc['1NNA', k]
        ax.scatter(x, y, s=60, c=grp.get(n, 'tab:blue'), zorder=3, marker='*' if n.startswith('Real') else 'o')
        ax.annotate(n, (x, y), xytext=(5, 4), textcoords='offset points', fontsize=8)
    mx, my = mix.loc['G2+G4', 'copia_mean'], 100 * mix.loc['G2+G4', 'NNA_mean']
    ax.scatter(mx, my, s=70, marker='D', c='tab:green', zorder=3)
    ax.annotate('G2+G4', (mx, my), xytext=(5, -11), textcoords='offset points', fontsize=8)
    ax.axhline(50, ls=':', c='gray')
    ax.text(2.05, 50.8, 'indistinguible', fontsize=7, color='gray', ha='right')
    ax.set_xlabel('Novedad (distancia a la fuente / distancia real–real)')
    ax.set_ylabel('1-NNA (%)')
    ax.legend(handles=[Line2D([], [], marker='o', ls='', c='tab:blue', label='Grupo 3: aprenden de reales'),
                       Line2D([], [], marker='o', ls='', c='tab:orange', label='Grupo 1: reglas'),
                       Line2D([], [], marker='o', ls='', c='tab:red', label='Grupo 2: algoritmo'),
                       Line2D([], [], marker='D', ls='', c='tab:green', label='Mezcla')], fontsize=7, loc='upper left')
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, 'fidelidad_novedad.pdf'))

    # W1n por rasgo
    f = pd.read_csv(os.path.join(args.work, 'eval_full.csv'), index_col=0)
    cols = ['REAL train (ref.)', 'iid_radius', 'allometric_a025', 'recombine', 'hybrid', 'procedural', 'rules',
            'colonization']
    rows = [r for r in f.index if r.startswith('W1n:') and not r.startswith('W1n:br_')]
    M = f.loc[rows, cols]
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    im = ax.imshow(M.values, cmap='viridis_r', vmin=0, vmax=1.5, aspect='auto')
    ax.set_xticks(range(len(cols)), [NAMES[c] for c in cols], rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(len(rows)), [r[4:] for r in rows], fontsize=7)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M.values[i, j]
            ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=5.5, color='w' if v > 0.8 else 'k')
    fig.colorbar(im, ax=ax, label='W1 normalizada')
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, 'w1_rasgos.pdf'))

    # árbol real + un sintético de cada generador
    gens = ['iid_radius', 'allometric_a025', 'allometric_a050', 'recombine', 'hybrid', 'procedural', 'rules',
            'colonization']
    subprocess.run([sys.executable, os.path.join(HERE, 'render.py'), args.tree, '--work', args.work, '--out', args.out,
                    '--gens', *gens, '--labels', 'G0', 'G1 α=0,25', 'G1 α=0,5', 'G2', 'G3', 'G4', 'G5', 'G6'],
                   check=True)
    os.replace(os.path.join(args.out, f'{args.tree}_s0.png'), os.path.join(args.out, 'generadores.png'))
    print('figuras ->', os.path.abspath(args.out))


if __name__ == '__main__':
    main()

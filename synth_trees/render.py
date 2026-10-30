"""Vista lateral (x-z) de un árbol real y sus sintéticos, lado a lado."""
import argparse
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

import qsm


def draw(ax, t, title):
    seg = np.stack([t.start[:, [0, 2]], t.end[:, [0, 2]]], axis=1)
    seg -= np.array([t.start[0, 0], t.start[0, 2]])
    lw = np.clip(t.radius * 60, 0.2, 8)
    col = plt.cm.viridis(np.clip(t.order / 6, 0, 1))
    ax.add_collection(LineCollection(seg, linewidths=lw, colors=col, capstyle='round'))
    ax.set_title(title, fontsize=13)
    ax.set_aspect('equal')
    ax.autoscale()
    ax.axis('off')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tree')
    ap.add_argument('--work', default='work')
    ap.add_argument('--gens', nargs='+', default=['iid_radius', 'allometric_a025', 'allometric_a050', 'recombine', 'hybrid', 'procedural'])
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default='work/figs')
    ap.add_argument('--labels', nargs='+', help='títulos de los paneles sintéticos (por defecto, el nombre del generador)')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    trees = [(qsm.load_npz(os.path.join(args.work, 'real', args.tree + '.npz')), 'Real')]
    for i, g in enumerate(args.gens):
        p = os.path.join(args.work, 'syn_' + g, f'{args.tree}__{g}_s{args.seed}.npz')
        trees.append((qsm.load_npz(p), args.labels[i] if args.labels else g))
    fig, axs = plt.subplots(1, len(trees), figsize=(3.2 * len(trees), 4.5))
    for ax, (t, title) in zip(axs, trees):
        draw(ax, t, title)
    lim_x = max(ax.get_xlim()[1] - ax.get_xlim()[0] for ax in axs) / 2
    lim_y = max(ax.get_ylim()[1] for ax in axs)
    for ax in axs:
        c = sum(ax.get_xlim()) / 2
        ax.set_xlim(c - lim_x, c + lim_x)
        ax.set_ylim(-0.5, lim_y)
    fig.tight_layout()
    path = os.path.join(args.out, f'{args.tree}_s{args.seed}.png')
    fig.savefig(path, dpi=110)
    print(path)


if __name__ == '__main__':
    main()

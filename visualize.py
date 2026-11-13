#!/usr/bin/env python3
"""Render QSM cylinder skeletons as PNG for quick visualisation.

Each cylinder is drawn as a 3-D line segment from start to start+length*axis,
coloured by branch order and with linewidth proportional to radius.
"""
import argparse
import os

import numpy as np
import scipy.io as sio

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection


def load_qsm(path):
    d = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    key = 'QSM' if 'QSM' in d else next(k for k in d if not k.startswith('__'))
    return d[key]


def render(q, out_png, title=''):
    cy = q.cylinder
    st = cy.start.astype(np.float64)
    end = st + cy.length.astype(np.float64)[:, None] * cy.axis.astype(np.float64)
    bo = cy.BranchOrder.astype(np.float64)
    r = cy.radius.astype(np.float64)

    cmap = plt.get_cmap('viridis')
    segs = list(zip(st, end))
    lw = np.clip(r * 6.0, 0.3, 5.0)
    order_norm = (bo - bo.min()) / (bo.max() - bo.min() + 1e-9)

    fig = plt.figure(figsize=(5, 9))
    ax = fig.add_subplot(111, projection='3d')
    lc = Line3DCollection(segs, linewidths=lw, colors=cmap(order_norm))
    ax.add_collection3d(lc)

    allpts = np.concatenate([st, end], axis=0)
    c = allpts.mean(axis=0)
    span = (allpts.max(axis=0) - allpts.min(axis=0)).max() * 0.5
    ax.set_xlim(c[0] - span, c[0] + span)
    ax.set_ylim(c[1] - span, c[1] + span)
    ax.set_zlim(c[2] - span, c[2] + span)
    ax.set_box_aspect((1, 1, 1))
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=8)

    fig.savefig(out_png, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print('wrote', out_png)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files', nargs='+', help='.mat QSM files to render.')
    ap.add_argument('--outdir', default='viz', help='Output dir for PNGs.')
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    for f in args.files:
        q = load_qsm(f)
        stem = os.path.basename(f)[:-4]
        render(q, os.path.join(args.outdir, stem + '.png'), title=stem)


if __name__ == '__main__':
    main()

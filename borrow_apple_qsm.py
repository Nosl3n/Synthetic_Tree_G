#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Angel Marquez Aguilar
# Output data from the Bibaum tree: CC BY 4.0, provenance and credit in apple/README.md.
"""Import the real Bibaum apple-tree QSM and compare it with procedural and tropical trees.

Converts the GroIMP `.qsm` CSV (id,parent,start,end,radius,length,branch_order) into
the same `synth_trees/qsm.py` Tree format as the tropical trees, then renders it
side-by-side (real apple | procedural apple | tropical).
"""
import os, sys, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'synth_trees'))
import qsm

# GroIMP .qsm exports of the Bibaum A tree (not in this repository; the derived apple/bibaum_*.npz are).
BIBAUM_QSM_DIR = os.environ.get('BIBAUM_QSM_DIR', os.path.join(HERE, 'bibaum_qsm'))
BIBAUM = os.path.join(BIBAUM_QSM_DIR, 'bibaum_a_prepruned.qsm')
BIBAUM_PRUNED = os.path.join(BIBAUM_QSM_DIR, 'bibaum_a_pruned.qsm')


def qsm_csv_to_tree(path, name, species):
    df = pd.read_csv(path)
    df = df.sort_values('id').reset_index(drop=True)
    parent = df['parent'].to_numpy(np.int64) - 1          # 1-based -> 0-based (-1 = root)
    order_in = df['branch_order'].to_numpy(np.int64)
    start = df[['start_x', 'start_y', 'start_z']].to_numpy(float)
    end = df[['end_x', 'end_y', 'end_z']].to_numpy(float)
    vec = end - start
    length = np.linalg.norm(vec, axis=1)
    axis = vec / np.maximum(length, 1e-9)[:, None]
    radius = df['radius'].to_numpy(float)

    # reconstruct extension: the child with the SAME branch order is the continuation
    n = len(parent)
    children = [[] for _ in range(n)]
    for i in range(n):
        if parent[i] >= 0:
            children[parent[i]].append(i)
    ext = np.full(n, -1, dtype=np.int64)
    for i in range(n):
        for c in children[i]:
            if order_in[c] == order_in[i]:
                ext[i] = c
                break

    t = qsm.Tree(start, axis, length, radius, parent, ext, name, species)
    t.recompute_topology()
    # sanity: reconstructed order should match the CSV's branch_order
    assert np.array_equal(t.order, order_in), 'order mismatch vs CSV branch_order'
    return t


def render_ax(ax, t, title):
    st = t.start.astype(float)
    en = st + t.axis.astype(float) * t.length.astype(float)[:, None]
    bo = t.order.astype(float)
    cmap = plt.get_cmap('viridis')
    lw = np.clip(t.radius.astype(float) * 45, 0.4, 5.0)
    norm = (bo - bo.min()) / (bo.max() - bo.min() + 1e-9)
    ax.add_collection3d(Line3DCollection(list(zip(st, en)), linewidths=lw, colors=cmap(norm)))
    allpts = np.concatenate([st, en])
    c = allpts.mean(0); span = (allpts.max(0) - allpts.min(0)).max() * 0.5 + 0.05
    ax.set_xlim(c[0] - span, c[0] + span); ax.set_ylim(c[1] - span, c[1] + span)
    ax.set_zlim(c[2] - span, c[2] + span)
    ax.set_box_aspect((1, 1, 1)); ax.set_axis_off(); ax.set_title(title, fontsize=9)


def stats(t):
    h = float(t.end[:, 2].max() - t.start[0, 2])
    vol = float(np.pi * t.radius ** 2 * t.length * 1000.0).sum() if False else float((np.pi * t.radius**2 * t.length * 1000.0).sum())
    return dict(height=h, n_cyl=t.n, n_branch=int(t.branch.max() + 1), vol_L=vol)


def main():
    os.makedirs(f'{HERE}/apple', exist_ok=True)
    bibaum = qsm_csv_to_tree(BIBAUM, 'bibaum_prepruned', 'MALUS')
    qsm.save_npz(bibaum, f'{HERE}/apple/bibaum_prepruned.npz')
    print('bibaum (real apple):', stats(bibaum))

    # procedural apple (from make_apple_comparison)
    import make_apple_comparison as mac
    proc = mac.build_apple(seed=0)

    mats = sorted(glob.glob(f'{HERE}/mat/MultipleQSMModels/*.mat'))
    trop = qsm.load_mat(mats[0])

    fig = plt.figure(figsize=(13, 5))
    ax1 = fig.add_subplot(1, 3, 1, projection='3d')
    ax2 = fig.add_subplot(1, 3, 2, projection='3d')
    ax3 = fig.add_subplot(1, 3, 3, projection='3d')
    render_ax(ax1, bibaum, f"Apple tree (real, Bibaum)  h={stats(bibaum)['height']:.2f} m")
    render_ax(ax2, proc, f"Apple tree (procedural)  h={stats(proc)['height']:.2f} m")
    render_ax(ax3, trop, f"Tropical tree ({trop.species})  h={stats(trop)['height']:.2f} m")
    fig.tight_layout()
    out = f'{HERE}/apple/apple_real_vs_tropical.png'
    fig.savefig(out, dpi=150)
    print('tropical:', stats(trop), trop.name)
    print('wrote', out)

    # pruned apple (post-pruning) -> npz
    pruned = qsm_csv_to_tree(BIBAUM_PRUNED, 'bibaum_pruned', 'MALUS')
    qsm.save_npz(pruned, f'{HERE}/apple/bibaum_pruned.npz')
    print('pruned (real apple):', stats(pruned))

    # clean 2-panel deck image: real apple vs tropical
    fig2 = plt.figure(figsize=(9, 5))
    d1 = fig2.add_subplot(1, 2, 1, projection='3d')
    d2 = fig2.add_subplot(1, 2, 2, projection='3d')
    render_ax(d1, bibaum, "Orchard apple tree (real, Bibaum)\n2.1 m · 131 cylinders · 66 branches")
    render_ax(d2, trop, f"Tropical tree ({trop.species})\n32 m · 1116 cylinders · 201 branches")
    fig2.tight_layout()
    deck = f'{HERE}/apple/apple_vs_tropical_deck.png'
    fig2.savefig(deck, dpi=160)
    print('wrote', deck)


if __name__ == '__main__':
    main()

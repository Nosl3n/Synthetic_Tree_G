#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Angel Marquez Aguilar
"""High-quality render of a single QSM tree: solid, shaded cylinders."""
import os, sys, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'synth_trees'))
import qsm


def render_solid(t, out, n_circ=12, dpi=200):
    light = np.array([0.4, -0.3, 0.85]); light /= np.linalg.norm(light)
    st = t.start.astype(float)
    ax = t.axis.astype(float)
    L = t.length.astype(float)
    r = t.radius.astype(float)
    order = t.order.astype(float)
    cmap = plt.get_cmap('viridis')
    norm = (order - order.min()) / (order.max() - order.min() + 1e-9)

    verts, colors = [], []
    for i in range(len(st)):
        a = ax[i] / np.linalg.norm(ax[i])
        ref = np.array([1, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1, 0])
        u = np.cross(a, ref); u /= np.linalg.norm(u)
        v = np.cross(a, u)
        th = np.linspace(0, 2 * np.pi, n_circ, endpoint=False)
        circ = np.outer(np.cos(th), u) + np.outer(np.sin(th), v)
        s0, s1 = st[i], st[i] + a * L[i]
        ring0 = s0 + circ * r[i]
        ring1 = s1 + circ * r[i]
        base = np.array(cmap(norm[i])[:3])
        for j in range(n_circ):
            jn = (j + 1) % n_circ
            mid = (ring0[j] + ring1[j]) / 2
            radial = mid - (s0 + s1) / 2
            radial /= np.linalg.norm(radial) + 1e-9
            lam = max(0.0, float(np.dot(radial, light)))
            colors.append(tuple(np.clip(base * (0.45 + 0.55 * lam), 0, 1)))
            verts.append([ring0[j], ring0[jn], ring1[jn], ring1[j]])

    pc = Poly3DCollection(verts, facecolors=colors, edgecolors='none')
    fig = plt.figure(figsize=(9, 13))
    axx = fig.add_subplot(111, projection='3d')
    axx.add_collection3d(pc)
    allpts = np.vstack([st, st + ax * L[:, None]])
    c = allpts.mean(0); span = (allpts.max(0) - allpts.min(0)).max() * 0.5
    axx.set_xlim(c[0] - span, c[0] + span); axx.set_ylim(c[1] - span, c[1] + span)
    axx.set_zlim(c[2] - span, c[2] + span)
    axx.set_box_aspect((1, 1, 1)); axx.set_axis_off()
    fig.savefig(out, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('wrote', out)


if __name__ == '__main__':
    mats = sorted(glob.glob(f'{HERE}/mat/MultipleQSMModels/*.mat'))
    tree = qsm.load_mat(mats[0])
    out = f'{HERE}/viz/{tree.name}_solid.png'
    render_solid(tree, out)
    print('tree:', tree.name, tree.species, 'cylinders:', tree.n)

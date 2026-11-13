#!/usr/bin/env python3
"""Generate a procedural apple-tree QSM and compare it with a tropical QSM.

Uses the same cylinder-table machinery (synth_trees/qsm.py) as the tropical trees,
so the apple tree is directly comparable (same format, same traits code).
"""
import os, sys, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection

HERE = '/home/angel/qsm_work'
sys.path.insert(0, os.path.join(HERE, 'synth_trees'))
import qsm


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def build_apple(seed=0):
    """Open-centre (vase) orchard apple tree: short trunk, wide spreading crown."""
    rng = np.random.default_rng(seed)
    S, A, L, R, P, E = [], [], [], [], [], []

    def add(start, axis, length, radius, parent):
        i = len(S)
        S.append(np.asarray(start, float)); A.append(_unit(axis))
        L.append(float(length)); R.append(float(radius)); P.append(parent); E.append(-1)
        return i

    def chain(start, axis, n, Ltot, r_base, r_tip, parent, cont=False):
        ids = []; s = np.asarray(start, float); p = parent; ax = _unit(axis)
        for k in range(n):
            r = r_base + (r_tip - r_base) * k / max(n - 1, 1)
            i = add(s, ax, Ltot / n, r, p)
            ids.append(i); s = s + ax * (Ltot / n); p = i
        for k in range(len(ids) - 1):
            E[ids[k]] = ids[k + 1]
        if cont and parent >= 0:
            E[parent] = ids[0]
        return ids

    up = np.array([0.0, 0.0, 1.0])
    # short trunk
    trunk = chain([0.0, 0.0, 0.0], up, 2, 0.55, 0.085, 0.06, -1)
    top = np.asarray(S[trunk[-1]]) + np.asarray(A[trunk[-1]]) * L[trunk[-1]]
    # 4 scaffold branches, wide angle (open centre)
    for k in range(4):
        az = 2 * np.pi * k / 4 + rng.uniform(-0.3, 0.3)
        zen = np.radians(rng.uniform(60, 80))
        ax = np.array([np.sin(zen) * np.cos(az), np.sin(zen) * np.sin(az), np.cos(zen)])
        scaff = chain(top, ax, 4, rng.uniform(1.3, 1.9), 0.045, 0.016, trunk[-1])
        # secondary branches along each scaffold
        for j in range(1, len(scaff)):
            if rng.random() < 0.8:
                pidx = scaff[j]
                sp = np.asarray(S[pidx]) + np.asarray(A[pidx]) * L[pidx]
                az2 = rng.uniform(0, 2 * np.pi)
                zen2 = np.radians(rng.uniform(35, 65))
                ax2 = np.array([np.sin(zen2) * np.cos(az2), np.sin(zen2) * np.sin(az2), np.cos(zen2)])
                chain(sp, ax2, 3, rng.uniform(0.4, 0.9), 0.02, 0.008, pidx)

    return qsm.Tree(np.array(S), np.array(A), np.array(L), np.array(R),
                    np.array(P, dtype=np.int64), np.array(E, dtype=np.int64),
                    'apple_procedural', 'MALUS').recompute_topology()


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
    h = t.end[:, 2].max() - t.start[0, 2]
    vol = np.pi * t.radius ** 2 * t.length * 1000.0
    return dict(height=h, n_cyl=t.n, n_branch=int(t.branch.max() + 1), vol_L=vol.sum())


def main():
    os.makedirs(f'{HERE}/apple', exist_ok=True)
    apple = build_apple(seed=0)
    qsm.save_npz(apple, f'{HERE}/apple/apple_procedural.npz')

    mats = sorted(glob.glob(f'{HERE}/mat/MultipleQSMModels/*.mat'))
    trop = qsm.load_mat(mats[0])

    fig = plt.figure(figsize=(9, 6))
    ax1 = fig.add_subplot(1, 2, 1, projection='3d')
    ax2 = fig.add_subplot(1, 2, 2, projection='3d')
    render_ax(ax1, apple, f"Apple tree (procedural)  h={stats(apple)['height']:.2f} m")
    render_ax(ax2, trop, f"Tropical tree ({trop.species})  h={stats(trop)['height']:.2f} m")
    fig.tight_layout()
    out = f'{HERE}/apple/apple_vs_tropical.png'
    fig.savefig(out, dpi=150)
    print('apple:', stats(apple))
    print('tropical:', stats(trop), trop.name)
    print('wrote', out)


if __name__ == '__main__':
    main()

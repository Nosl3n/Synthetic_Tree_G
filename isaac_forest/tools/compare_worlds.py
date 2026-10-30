"""Compara los datos de sensores de v1 (solo árboles) y v2 (bosque ambientado).

Ambas versiones tienen los mismos árboles, posiciones y circuito, así que las
diferencias vienen solo de la ambientación (terreno, sotobosque, madera muerta,
rocas, árboles exteriores y cielo).

    python3 tools/compare_worlds.py --out ../paper/figs
Salidas: comparacion_v1_v2.json, figuras sensores_v1_v2.png, lidar_v1_v2.pdf, vistas_v1_v2.png
"""
import argparse
import glob
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from PIL import Image

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, HERE)
import dressing as DR  # noqa: E402

COL = np.array([[.55, .75, .95], [.62, .52, .36], [.45, .22, .05], [.9, .6, .2], [.15, .7, .25],
                [.25, .82, .35], [.67, .35, .78], [.47, .5, .59], [.5, .5, .5]])
NAMES = ['cielo/nada', 'suelo', 'tronco', 'rama', 'hoja', 'sotobosque', 'madera muerta', 'roca', 'otro']
WORLDS = {'v1': 'v1_arboles', 'v2': 'v2_bosque'}


def stats(d):
    m = json.load(open(os.path.join(d, 'meta.json')))
    fs = sorted(glob.glob(os.path.join(d, 'frames', '*.npz')))
    T = m.get('terrain') or dict(kx=[], ky=[], a=[], ph=[])
    K = len(NAMES)
    cnt, semc = np.zeros(K), np.zeros(K)
    npts, trunk_per_tree, trees_seen, gerr, rmin, depth_med = [], [], [], [], [], []
    for f in fs[::2]:
        z = np.load(f)
        L, P, tr = z['lidar_label'], z['lidar_xyz'], z['lidar_tree']
        cnt += np.bincount(L, minlength=K)[:K]
        semc += np.bincount(z['sem'].ravel(), minlength=K)[:K]
        npts.append(len(L))
        inner = (tr >= 0) & (tr < 100) & (L == 2)
        seen = np.unique(tr[inner])
        trees_seen.append(len(seen))
        trunk_per_tree.append(inner.sum() / max(len(seen), 1))
        g = P[L == 1]
        gerr.append(np.median(np.abs(g[:, 2] - DR.terrain_height(T, g[:, 0], g[:, 1]))))
        rmin.append(np.percentile(np.linalg.norm(z['lidar_xyz_sensor'], axis=1), 0.1))
        dep = z['depth'].astype(float)
        depth_med.append(np.median(dep[dep > 0]))
    return dict(frames=len(fs), points_per_scan=float(np.mean(npts)), points_per_scan_sd=float(np.std(npts)),
                lidar_pct={n: float(100 * c / cnt.sum()) for n, c in zip(NAMES, cnt) if c},
                camera_pct={n: float(100 * c / semc.sum()) for n, c in zip(NAMES, semc) if c},
                inner_trees_seen_per_scan=float(np.mean(trees_seen)),
                trunk_points_per_seen_tree=float(np.mean(trunk_per_tree)),
                ground_err_median_m=float(np.median(gerr)), min_range_m=float(np.min(rmin)),
                depth_median_m=float(np.median(depth_med)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rec', default=os.path.join(HERE, 'recordings'))
    ap.add_argument('--shots', default=os.path.join(HERE, 'screenshots'))
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'paper', 'figs'))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    S = {v: stats(os.path.join(args.rec, w)) for v, w in WORLDS.items()}
    json.dump(S, open(os.path.join(args.rec, 'comparacion_v1_v2.json'), 'w'), indent=1)
    for v, s in S.items():
        print(v, json.dumps({k: (round(x, 3) if isinstance(x, float) else
                                 {a: round(b, 2) for a, b in x.items()} if isinstance(x, dict) else x)
                             for k, x in s.items()}, ensure_ascii=False))

    # cámara: mismo fotograma (misma pose) en v1 y v2
    fig, ax = plt.subplots(2, 3, figsize=(14, 5.6))
    for r, (v, w) in enumerate(WORLDS.items()):
        fs = sorted(glob.glob(os.path.join(args.rec, w, 'frames', '*.npz')))
        z = np.load(fs[len(fs) // 3])
        ax[r, 0].imshow(z['rgb'])
        im = ax[r, 1].imshow(z['depth'].astype(float), cmap='turbo', vmin=0, vmax=40)
        ax[r, 2].imshow(z['sem'], cmap=ListedColormap(COL), vmin=0, vmax=len(NAMES) - 1, interpolation='nearest')
        for a in ax[r]:
            a.set_xticks([]), a.set_yticks([])
        ax[r, 0].set_ylabel(v, fontsize=13, rotation=0, labelpad=18)
    for a, t in zip(ax[0], ['RGB', 'Profundidad (m)', 'Segmentación']):
        a.set_title(t)
    cax = fig.add_axes([0.92, 0.2, 0.012, 0.65])
    fig.colorbar(im, cax=cax, label='profundidad (m)')
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=COL[i], label=NAMES[i]) for i in (0, 1, 2, 3, 5, 6, 7)], loc='lower center',
               ncol=7, fontsize=9, frameon=False)
    fig.subplots_adjust(left=0.05, right=0.9, bottom=0.1, wspace=0.03, hspace=0.06)
    fig.savefig(os.path.join(args.out, 'sensores_v1_v2.png'), dpi=130)

    # LiDAR: corte lateral acumulado y reparto por clase
    fig = plt.figure(figsize=(13, 6.2))
    gs = fig.add_gridspec(2, 3)
    for r, (v, w) in enumerate(WORLDS.items()):
        fs = sorted(glob.glob(os.path.join(args.rec, w, 'frames', '*.npz')))
        Ps, Cs = [], []
        for i, f in enumerate(fs[::4]):
            z = np.load(f)
            k = np.random.default_rng(i).choice(len(z['lidar_label']), min(len(z['lidar_label']), 8000), replace=False)
            Ps.append(z['lidar_xyz'][k])
            Cs.append(z['lidar_label'][k])
        P, C = np.concatenate(Ps), np.concatenate(Cs)
        a = fig.add_subplot(gs[r, :2])
        s = (np.abs(P[:, 1]) < 8) & (C > 1) & (np.abs(P[:, 0]) < 60)
        o = np.argsort(C[s])
        a.scatter(P[s][o, 0], P[s][o, 2], s=0.15, c=COL[C[s][o]], rasterized=True)
        a.set_aspect('equal'), a.set_ylabel('z (m)'), a.set_xlim(-60, 60), a.set_ylim(-1.5, 32)
        a.set_title(f'{v}: LiDAR acumulado, corte |y| < 8 m (sin suelo)', fontsize=10)
        if r == 1:
            a.set_xlabel('x (m)')
        else:
            a.set_xticklabels([])
    a = fig.add_subplot(gs[:, 2])
    cls = [1, 2, 3, 5, 6, 7]
    x = np.arange(len(cls))
    for j, v in enumerate(WORLDS):
        vals = [S[v]['lidar_pct'].get(NAMES[c], 0) for c in cls]
        a.bar(x + (j - 0.5) * 0.38, vals, 0.38, label=v, color=COL[cls], edgecolor='k',
              hatch='' if v == 'v1' else '//')
    a.set_xticks(x, [NAMES[c] for c in cls], rotation=35, ha='right')
    a.set_ylabel('% de puntos LiDAR'), a.set_yscale('log'), a.legend(), a.set_title('Puntos por clase', fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, 'lidar_v1_v2.pdf'), dpi=200)

    # vistas del simulador lado a lado
    pairs = ['08_sendero', '03_a_pie_entre_arboles', '01_aerea']
    fig, ax = plt.subplots(len(pairs), 2, figsize=(12, 3.6 * len(pairs)))
    for r, p in enumerate(pairs):
        for c, (v, w) in enumerate(WORLDS.items()):
            ax[r, c].imshow(Image.open(os.path.join(args.shots, w, p + '.png')))
            ax[r, c].axis('off')
            if r == 0:
                ax[r, c].set_title({'v1': 'v1: solo árboles', 'v2': 'v2: bosque ambientado'}[v], fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, 'vistas_v1_v2.png'), dpi=110)


if __name__ == '__main__':
    main()

"""Rasgos de árbol y de rama calculados con el mismo código para reales y sintéticos.

Unidades: metros, litros (volumen) y grados.
"""
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, QhullError

TAPER_H = np.round(np.arange(0.1, 1.0, 0.1), 1)   # alturas relativas del tronco


def _ang(a, b):
    return np.degrees(np.arccos(np.clip(np.sum(a * b, axis=-1), -1, 1)))


def branch_table(t):
    """Una fila por rama (excepto el tronco)."""
    first = np.where(t.pos == 1)[0]
    nb = t.branch.max() + 1
    blen = np.bincount(t.branch, weights=t.length, minlength=nb)
    base_z = t.start[0, 2]
    height = t.end[:, 2].max() - base_z
    rows = []
    nchild = np.bincount(t.branch[t.parent[first[first > 0]]], minlength=nb)
    for i in first:
        p = t.parent[i]
        if p < 0:
            continue
        b, pb = t.branch[i], t.branch[p]
        rows.append(dict(
            order=int(t.order[i]),
            radius=t.radius[i],
            diam_ratio=t.radius[i] / t.radius[p],
            length=blen[b],
            length_ratio=blen[b] / blen[pb],
            insert_angle=_ang(t.axis[i], t.axis[p]),
            zenith=_ang(t.axis[i], np.array([0, 0, 1.0])),
            rel_height=(t.start[i, 2] - base_z) / height,
            n_children=int(nchild[b]),
            child_density=nchild[b] / blen[b],
        ))
    return pd.DataFrame(rows, columns=['order', 'radius', 'diam_ratio', 'length', 'length_ratio',
                                       'insert_angle', 'zenith', 'rel_height', 'n_children',
                                       'child_density'])


def pipe_ratios(t, min_r=0.02):
    """Σr²(hijos)/r²(padre) en cilindros con ≥2 hijos y radio > min_r."""
    ch = t.children()
    out = [np.sum(t.radius[c] ** 2) / t.radius[i] ** 2
           for i, c in enumerate(ch) if len(c) >= 2 and t.radius[i] > min_r]
    return np.array(out)


def trunk_profile(t):
    """Radio del tronco a cada altura relativa de TAPER_H, normalizado por r(1,3 m)."""
    tr = np.where(t.branch == 0)[0]
    z0 = t.start[0, 2]
    zs, ze = t.start[tr, 2] - z0, t.end[tr, 2] - z0
    zmid = (zs + ze) / 2

    def r_at(z):
        k = np.where((zs <= z) & (ze >= z))[0]
        return t.radius[tr[k[0]]] if len(k) else t.radius[tr[np.argmin(np.abs(zmid - z))]]

    r13 = r_at(1.3)
    trunk_h = ze.max()
    return r13, trunk_h, np.array([r_at(h * trunk_h) / r13 for h in TAPER_H])


def tree_traits(t):
    vol = np.pi * t.radius ** 2 * t.length * 1000.0
    base_z = t.start[0, 2]
    height = t.end[:, 2].max() - base_z
    r13, trunk_h, taper = trunk_profile(t)
    vol_trunk = vol[t.branch == 0].sum()
    crown = np.vstack([t.start[t.order >= 1, :2], t.end[t.order >= 1, :2]])
    try:
        hull = ConvexHull(crown)
        hv = crown[hull.vertices]
        crown_area = hull.volume
    except (QhullError, ValueError):      # copa degenerada (casi una línea) o < 3 puntos
        hv, crown_area = crown, 0.0
    crown_diam = np.max(np.linalg.norm(hv[:, None] - hv[None], axis=-1)) if len(hv) else 0.0
    bt = branch_table(t)
    o1 = bt[bt.order == 1]
    big1 = o1[o1.length > 1.0]
    cbh = ((t.start[t.pos == 1][t.order[t.pos == 1] == 1][:, 2].min() - base_z) / height
           if len(o1) else np.nan)
    pr = pipe_ratios(t)
    d = dict(
        height=height, dbh=2 * r13, trunk_height=trunk_h,
        vol_total=vol.sum(), vol_trunk=vol_trunk,
        branch_vol_frac=1 - vol_trunk / vol.sum(),
        len_total=t.length.sum(),
        n_branches=len(bt), max_order=int(t.order.max()), n_cyl=t.n,
        n_br_o1=int((bt.order == 1).sum()), n_br_o2=int((bt.order == 2).sum()),
        n_br_o3=int((bt.order == 3).sum()),
        crown_area=crown_area, crown_diam=crown_diam,
        crown_base_rel=cbh,
        first_big_branch_rel=(big1.rel_height.min() if len(big1) else np.nan),
        o1_angle_med=o1.insert_angle.median(),
        o1_diam_ratio_med=o1.diam_ratio.median(),
        o1_child_density=o1.child_density.median(),
        pipe_med=np.median(pr) if len(pr) else np.nan,
    )
    for o in (1, 2, 3):
        d[f'vol_frac_o{o}'] = vol[t.order == o].sum() / vol.sum()
    for h, v in zip(TAPER_H, taper):
        d[f'taper_{int(h * 10):02d}'] = v
    return d

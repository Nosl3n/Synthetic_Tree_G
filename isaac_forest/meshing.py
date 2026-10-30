"""Malla continua y suavizada de un árbol QSM (un tubo por rama).

Diferencias con un cilindro por segmento:
  - los huecos de TreeQSM entre cilindros consecutivos se cierran (cada unión es
    el punto medio entre el final de uno y el inicio del siguiente);
  - cada rama hija empieza en el eje de su madre, así que nace desde dentro de ella;
  - el eje se alisa (Laplaciano, más fuerte cuanto más gruesa la rama) y se suaviza (Chaikin) y los anillos consecutivos se comparten, con marcos
    de transporte paralelo (sin torsión), normales suaves y UVs a lo largo de la rama;
  - las puntas se cierran en cono.
"""
import numpy as np


def _chaikin(P, R, iters):
    for _ in range(iters):
        if len(P) < 3:
            break
        Q = 0.75 * P[:-1] + 0.25 * P[1:]
        S = 0.25 * P[:-1] + 0.75 * P[1:]
        P2 = np.empty((2 * len(Q), 3))
        P2[0::2], P2[1::2] = Q, S
        RQ = 0.75 * R[:-1] + 0.25 * R[1:]
        RS = 0.25 * R[:-1] + 0.75 * R[1:]
        R2 = np.empty(2 * len(RQ))
        R2[0::2], R2[1::2] = RQ, RS
        P = np.vstack([P[:1], P2, P[-1:]])
        R = np.r_[R[0], R2, R[-1]]
    return P, R


def _laplacian(P, iters, lam=0.5):
    """Alisa el eje (extremos fijos): quita el zigzag del QSM sin cambiar la forma general."""
    P = P.copy()
    for _ in range(iters):
        P[1:-1] += lam * (0.5 * (P[:-2] + P[2:]) - P[1:-1])
    return P


def _frames(P):
    """Tangentes y normales por transporte paralelo a lo largo de la polilínea."""
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    N = np.zeros_like(P)
    ref = np.array([1.0, 0, 0]) if abs(T[0, 0]) < 0.9 else np.array([0, 1.0, 0])
    N[0] = ref - T[0] * np.dot(ref, T[0])
    N[0] /= np.linalg.norm(N[0])
    for i in range(1, len(P)):
        n = N[i - 1] - T[i] * np.dot(N[i - 1], T[i])
        L = np.linalg.norm(n)
        N[i] = n / L if L > 1e-9 else N[i - 1]
    B = np.cross(T, N)
    return T, N, B


def _sides(r):
    return 20 if r > 0.15 else 14 if r > 0.05 else 9 if r > 0.02 else 6


def tree_mesh(t, R=np.eye(3), offset=np.zeros(3), tile=0.6, tip_frac=0.5, lod=False):
    """Devuelve {'trunk': malla, 'branch': malla}; cada malla es un dict con
    points, normals, uvs (por vértice), counts, indices.

    lod=True: versión ligera para árboles lejanos (mitad de lados, menos suavizado,
    sin las ramitas de menos de 6 mm)."""
    origin = t.start[0]
    S = (t.start - origin) @ R.T + offset
    A = t.axis @ R.T
    E = S + A * t.length[:, None]
    nb = t.branch.max() + 1
    cyl = [[] for _ in range(nb)]
    for i in np.lexsort((t.pos, t.branch)):
        cyl[t.branch[i]].append(i)
    out = {c: dict(points=[], normals=[], uvs=[], counts=[], indices=[], n=0) for c in ('trunk', 'branch')}
    for b in range(nb):
        idx = np.array(cyl[b])
        r = t.radius[idx]
        if lod and r[0] < 0.006:
            continue
        # eje: inicio, uniones (punto medio de los huecos) y final
        joints = 0.5 * (E[idx[:-1]] + S[idx[1:]])
        P = np.vstack([S[idx[:1]], joints, E[idx[-1:]]])
        Rr = np.r_[r[0], 0.5 * (r[:-1] + r[1:]), r[-1] * tip_frac]
        p = t.parent[idx[0]]
        if p >= 0:
            # nacer desde el eje de la madre: punto del eje más cercano al inicio de la rama
            s_along = np.clip(np.dot(S[idx[0]] - S[p], A[p]), 0, t.length[p])
            base = S[p] + A[p] * s_along
            if np.linalg.norm(P[0] - base) > 1e-4:
                P = np.vstack([base, P])
                Rr = np.r_[min(r[0], t.radius[p] * 0.95), Rr]
        # quitar puntos casi duplicados
        keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-4]
        P, Rr = P[keep], Rr[keep]
        if len(P) < 2:
            continue
        # más alisado cuanto más grueso (un tronco real no zigzaguea cada 20 cm)
        P = _laplacian(P, int(np.clip(r[0] / 0.02, 1, 12)))
        P, Rr = _chaikin(P, Rr, 1 if lod else (2 if r[0] > 0.01 else 1))
        T, N, B = _frames(P)
        k = max(4, _sides(r[0]) // 2) if lod else _sides(r[0])
        th = np.linspace(0, 2 * np.pi, k + 1)            # k+1: vértice repetido para la costura de UV
        ring_dir = (np.cos(th)[None, :, None] * N[:, None] + np.sin(th)[None, :, None] * B[:, None])
        V = P[:, None] + ring_dir * Rr[:, None, None]       # (m, k+1, 3)
        m = len(P)
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        reps = max(1, round(2 * np.pi * r[0] / tile))
        U = np.broadcast_to(th / (2 * np.pi) * reps, (m, k + 1))
        Vv = np.broadcast_to((arc / tile)[:, None], (m, k + 1))
        cls = 'trunk' if t.order[idx[0]] == 0 else 'branch'
        o = out[cls]
        base_i = o['n']
        ii = np.arange(m - 1)[:, None] * (k + 1) + np.arange(k)[None]
        quads = np.stack([ii, ii + 1, ii + k + 2, ii + k + 1], -1).reshape(-1, 4) + base_i
        # punta cerrada: abanico al último punto del eje + un poco más
        tip = P[-1] + T[-1] * Rr[-1] * 2
        tip_i = base_i + m * (k + 1)
        last = base_i + (m - 1) * (k + 1) + np.arange(k)
        tris = np.stack([last, last + 1, np.full(k, tip_i)], -1)
        o['points'] += [V.reshape(-1, 3), tip[None]]
        o['normals'] += [ring_dir.reshape(-1, 3), T[-1][None]]
        o['uvs'] += [np.c_[U.reshape(-1), Vv.reshape(-1)], np.array([[0.5, arc[-1] / tile]])]
        o['counts'] += [np.full(len(quads), 4), np.full(k, 3)]
        o['indices'] += [quads.reshape(-1), tris.reshape(-1)]
        o['n'] = tip_i + 1
    res = {}
    for c, o in out.items():
        if o['n']:
            res[c] = dict(points=np.concatenate(o['points']), normals=np.concatenate(o['normals']),
                          uvs=np.concatenate(o['uvs']), counts=np.concatenate(o['counts']),
                          indices=np.concatenate(o['indices']))
    return res

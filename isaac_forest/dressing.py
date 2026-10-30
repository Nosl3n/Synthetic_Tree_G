"""Ambientación del bosque: terreno, circuito, sotobosque, madera muerta y rocas.

Solo numpy + pxr: lo usan build_forest.py (crear la escena) y run_sensors.py
(altura del terreno y circuito de la plataforma).
"""
import glob
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')


# ---------------------------------------------------------------- terreno

def terrain_params(rng, n=14, amp=0.9):
    """Suma de ondas con longitudes de 12 a 90 m (relieve suave de suelo de bosque)."""
    lam = np.exp(rng.uniform(np.log(12), np.log(90), n))
    ang = rng.uniform(0, 2 * np.pi, n)
    k = 2 * np.pi / lam
    a = amp * (lam / 90) ** 0.8 * rng.uniform(0.5, 1.0, n) / np.sqrt(n / 3)
    return dict(kx=(k * np.cos(ang)).tolist(), ky=(k * np.sin(ang)).tolist(), a=a.tolist(),
                ph=rng.uniform(0, 2 * np.pi, n).tolist())


def terrain_height(T, x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    h = np.zeros(np.broadcast(x, y).shape)
    for kx, ky, a, ph in zip(T['kx'], T['ky'], T['a'], T['ph']):
        h += a * np.sin(kx * x + ky * y + ph)
    return h


def terrain_mesh(T, half=130.0, step=1.0):
    g = np.arange(-half, half + 1e-9, step)
    X, Y = np.meshgrid(g, g, indexing='xy')
    Z = terrain_height(T, X, Y)
    P = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    n = len(g)
    i = (np.arange(n - 1)[:, None] * n + np.arange(n - 1)[None]).ravel()
    quads = np.stack([i, i + 1, i + n + 1, i + n], 1)
    # normales por diferencias finitas
    dzdx = np.gradient(Z, step, axis=1)
    dzdy = np.gradient(Z, step, axis=0)
    N = np.c_[-dzdx.ravel(), -dzdy.ravel(), np.ones(Z.size)]
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, np.full(len(quads), 4), quads.ravel(), N


# ---------------------------------------------------------------- circuito

def plan_loop(xy_obstacles, half, clearance=2.5):
    """Circuito cerrado r(θ) = r0 + A·sin(kθ + φ) que pasa cerca de los árboles sin chocar."""
    xy = np.asarray(xy_obstacles)
    th = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    best = None
    for r0 in np.arange(6, half - 4, 1.0):
        for A in (0, 2, 4):
            for k in (2, 3, 4, 5):
                for ph in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                    r = r0 + A * np.sin(k * th + ph)
                    P = np.c_[r * np.cos(th), r * np.sin(th)]
                    d = np.linalg.norm(P[:, None] - xy[None], axis=-1).min(1)
                    if d.min() < clearance or np.abs(P).max() > half - 2:
                        continue
                    score = np.mean(np.sort(d)[: len(d) // 4])
                    if best is None or score < best[0]:
                        best = (score, P)
    return best[1]


def dist_to_path(path, xy):
    """Distancia de cada punto xy al circuito (polilínea cerrada)."""
    A = np.asarray(path)
    B = np.roll(A, -1, axis=0)
    xy = np.asarray(xy)[:, None]
    AB = B - A
    t = np.clip(np.sum((xy - A) * AB, -1) / np.maximum(np.sum(AB * AB, -1), 1e-12), 0, 1)
    return np.linalg.norm(xy - (A + t[..., None] * AB), axis=-1).min(1)


def path_lengths(path):
    P = np.asarray(path)
    seg = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)
    return np.r_[0, np.cumsum(seg)]


def pose_at(path, s, dist):
    P = np.asarray(path)
    d = dist % s[-1]
    i = np.searchsorted(s, d, side='right') - 1
    a = (d - s[i]) / (s[i + 1] - s[i])
    p0, p1 = P[i], P[(i + 1) % len(P)]
    return p0 + a * (p1 - p0), math.atan2(*(p1 - p0)[::-1])


# ---------------------------------------------------------------- objetos Poly Haven

def scatter(rng, n, r_max, avoid, r_min=0.0):
    """Puntos uniformes en un disco (o corona) que cumplen avoid(xy) -> bool."""
    out = np.zeros((0, 2))
    for _ in range(20):
        m = max(n * 3, 100)
        r = np.sqrt(rng.uniform(r_min ** 2, r_max ** 2, m))
        a = rng.uniform(0, 2 * np.pi, m)
        P = np.c_[r * np.cos(a), r * np.sin(a)]
        out = np.vstack([out, P[avoid(P)]])
        if len(out) >= n:
            break
    return out[:n]


def prototypes(stage, root, group, model, material_fn, max_variants=12, min_size=0.05, exclude=()):
    """Un prototipo por variante del modelo, centrado en xy y apoyado en z = 0.

    Devuelve [(ruta, tamaño xyz)]. Los materiales incluidos se desactivan y se
    sustituye por un OmniPBR propio (máscaras alfa de 8 bits)."""
    from pxr import Gf, Usd, UsdGeom, UsdShade
    f = glob.glob(os.path.join(ASSETS, 'props', group, model, '*.usdc'))[0]
    src = Usd.Stage.Open(f)
    dp = src.GetDefaultPrim()
    cache = UsdGeom.BBoxCache(0, ['default', 'render'])
    variants = [c for c in dp.GetChildren() if not c.GetName().startswith('_')
                and any(p.IsA(UsdGeom.Mesh) for p in Usd.PrimRange(c))
                and 'LOD1' not in c.GetName() and 'LOD2' not in c.GetName()
                and not any(e in c.GetName() for e in exclude)]
    variants = [v for v in variants if max(cache.ComputeWorldBound(v).ComputeAlignedRange().GetSize()) >= min_size]
    mat = material_fn(stage, model, os.path.join(os.path.dirname(f), 'textures'))
    out = []
    for k, v in enumerate(variants[:max_variants]):
        rg = cache.ComputeWorldBound(v).ComputeAlignedRange()
        c, lo = rg.GetMidpoint(), rg.GetMin()
        wrap = UsdGeom.Xform.Define(stage, f'{root}/{model}_{k}')
        UsdGeom.XformCommonAPI(wrap).SetTranslate(Gf.Vec3d(-c[0], -c[1], -lo[2]))
        asset = stage.DefinePrim(f'{wrap.GetPath()}/asset')
        asset.GetReferences().AddReference(f)
        for other in dp.GetChildren():
            if other.GetName() != v.GetName():
                stage.OverridePrim(f'{asset.GetPath()}/{other.GetName()}').SetActive(False)
        UsdShade.MaterialBindingAPI.Apply(wrap.GetPrim()).Bind(mat, UsdShade.Tokens.strongerThanDescendants)
        out.append((wrap.GetPath(), np.array(rg.GetSize())))
    return out


def instancer(stage, path, protos, idx, xyz, yaw, scale, label):
    from pxr import Gf, UsdGeom, UsdSemantics, Vt
    inst = UsdGeom.PointInstancer.Define(stage, path)
    inst.CreatePrototypesRel().SetTargets([p for p, _ in protos])
    inst.CreateProtoIndicesAttr(Vt.IntArray([int(i) for i in idx]))
    inst.CreatePositionsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, p)) for p in xyz]))
    inst.CreateOrientationsAttr(Vt.QuathArray([Gf.Quath(math.cos(a / 2), 0, 0, math.sin(a / 2)) for a in yaw]))
    inst.CreateScalesAttr(Vt.Vec3fArray([Gf.Vec3f(float(s), float(s), float(s)) for s in scale]))
    for p, _ in protos:
        UsdSemantics.LabelsAPI.Apply(stage.GetPrimAtPath(p), 'class').CreateLabelsAttr().Set([label])
    return inst

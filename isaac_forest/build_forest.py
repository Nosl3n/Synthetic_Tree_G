"""Arma un bosque pequeño en USD con árboles sintéticos (G2 recombine + G4 procedural).

Cada rama es un tubo continuo (meshing.py). Por árbol hay dos mallas: tronco
(orden 0) y ramas (orden >= 1), etiquetadas con UsdSemantics para que la cámara
y el LiDAR devuelvan la clase de cada píxel/punto.

Ambientación de bosque (dressing.py, desactivable con --bare): terreno ondulado
con hojarasca, anillo exterior de árboles sintéticos (horizonte de bosque),
sotobosque, madera muerta, rocas con musgo y cielo de selva (Poly Haven, CC0).

No necesita arrancar Isaac: usa el pxr del entorno de Isaac Sim.
    $ISAAC_PY build_forest.py --bare --out scenes/forest_v1_arboles.usd    # v1: solo árboles
    $ISAAC_PY build_forest.py                                             # v2: bosque ambientado
"""
import argparse
import json
import os
import sys

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdSemantics, UsdShade, Vt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'synth_trees'))
import qsm  # noqa: E402
from meshing import tree_mesh  # noqa: E402
import dressing as DR  # noqa: E402

GENS = {'recombine': 'G2', 'procedural': 'G4'}
COLORS = {'trunk': (0.30, 0.22, 0.16), 'branch': (0.38, 0.29, 0.21), 'ground': (0.27, 0.30, 0.16)}
ASSETS = os.path.join(HERE, 'assets')
BARKS = ['bark_brown_01', 'bark_brown_02', 'chinese_hackberry_bark', 'japanese_zelkova_bark']


def tube_mesh(start, axis, length, radius, sides_thick=12, sides_thin=6, r_thin=0.03):
    """Tubos abiertos (sin tapas) para todos los cilindros; devuelve puntos, conteos e índices."""
    pts, counts, idx = [], [], []
    off = 0
    for k in (sides_thick, sides_thin):
        sel = radius >= r_thin if k == sides_thick else radius < r_thin
        if not sel.any():
            continue
        s, a, L, r = start[sel], axis[sel], length[sel], radius[sel]
        ov = np.minimum(0.6 * r, 0.08)          # solape en ambos extremos: tapa los huecos entre cilindros
        s, L = s - a * ov[:, None], L + 2 * ov
        ref = np.where(np.abs(a[:, :1]) < 0.9, [[1.0, 0, 0]], [[0, 1.0, 0]])
        u = ref - a * np.sum(ref * a, 1, keepdims=True)
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        v = np.cross(a, u)
        th = np.linspace(0, 2 * np.pi, k, endpoint=False)
        ring = (np.cos(th)[None, :, None] * u[:, None] + np.sin(th)[None, :, None] * v[:, None]) * r[:, None, None]
        p0 = s[:, None] + ring
        p1 = (s + a * L[:, None])[:, None] + ring
        P = np.concatenate([p0, p1], 1)                        # (n, 2k, 3)
        n = len(s)
        base = off + np.arange(n)[:, None] * 2 * k
        j = np.arange(k)
        quad = np.stack([j, (j + 1) % k, k + (j + 1) % k, k + j], 1)    # (k, 4)
        idx.append((base[:, None, :] + quad[None]).reshape(-1))
        counts.append(np.full(n * k, 4))
        pts.append(P.reshape(-1, 3))
        off += n * 2 * k
    return np.concatenate(pts), np.concatenate(counts), np.concatenate(idx)


def material(stage, name, color):
    path = f'/World/Looks/{name}'
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, f'{path}/Shader')
    sh.CreateIdAttr('UsdPreviewSurface')
    sh.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    sh.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(0.85)
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), 'surface')
    return mat


def omnipbr(stage, path, name, tint=(1, 1, 1), scale=(1.0, 1.0), world_project=True):
    """Material PBR con texturas escaneadas (Poly Haven, CC0): proyectadas en coordenadas de
    mundo (suelo, tubos sin UV) o con las UVs de la malla (tubos suaves)."""
    tex = lambda kind: os.path.join(ASSETS, 'textures', name, f'{name}_{kind}_2k.jpg')
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, f'{path}/Shader')
    sh.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
    sh.SetSourceAsset('OmniPBR.mdl', 'mdl')
    sh.SetSourceAssetSubIdentifier('OmniPBR', 'mdl')
    A, F, C, B = (Sdf.ValueTypeNames.Asset, Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Color3f,
                  Sdf.ValueTypeNames.Bool)
    sh.CreateInput('diffuse_texture', A).Set(Sdf.AssetPath(tex('diff')))
    sh.CreateInput('normalmap_texture', A).Set(Sdf.AssetPath(tex('nor_gl')))
    sh.CreateInput('reflectionroughness_texture', A).Set(Sdf.AssetPath(tex('rough')))
    sh.CreateInput('reflection_roughness_texture_influence', F).Set(1.0)
    sh.CreateInput('ao_texture', A).Set(Sdf.AssetPath(tex('ao')))
    sh.CreateInput('ao_to_diffuse', F).Set(1.0)
    sh.CreateInput('diffuse_tint', C).Set(Gf.Vec3f(*tint))
    sh.CreateInput('specular_level', F).Set(0.3)
    sh.CreateInput('texture_scale', Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(*scale))
    if world_project:
        sh.CreateInput('project_uvw', B).Set(True)
        sh.CreateInput('world_or_object', B).Set(True)
    out = sh.CreateOutput('out', Sdf.ValueTypeNames.Token)
    for o in (mat.CreateSurfaceOutput('mdl'), mat.CreateVolumeOutput('mdl'), mat.CreateDisplacementOutput('mdl')):
        o.ConnectToSource(out)
    return mat


def add_mesh(stage, path, P, C, I, cls, mat, normals=None, uvs=None):
    m = UsdGeom.Mesh.Define(stage, path)
    if normals is not None:
        m.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(normals.astype(np.float32)))
        m.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    if uvs is not None:
        st = UsdGeom.PrimvarsAPI(m).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
        st.Set(Vt.Vec2fArray.FromNumpy(uvs.astype(np.float32)))
    m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)))
    m.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(C.astype(np.int32)))
    m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(I.astype(np.int32)))
    m.CreateSubdivisionSchemeAttr('none')
    m.CreateDisplayColorAttr([Gf.Vec3f(*COLORS[cls])])
    UsdSemantics.LabelsAPI.Apply(m.GetPrim(), 'class').CreateLabelsAttr().Set([cls])
    UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(mat)
    return m


def prop_material(stage, model, tdir):
    """OmniPBR con las texturas del modelo (alfa de 8 bits si tiene recortes)."""
    import glob
    t = lambda kind: (sorted(glob.glob(os.path.join(tdir, f'*_{kind}_*.jpg'))) +
                      sorted(glob.glob(os.path.join(tdir, f'*_{kind}_*.png'))) + [None])[0]
    path = f'/World/Looks/Prop_{model}'
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, f'{path}/Shader')
    sh.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
    sh.SetSourceAsset('OmniPBR.mdl', 'mdl')
    sh.SetSourceAssetSubIdentifier('OmniPBR', 'mdl')
    A, F, B = Sdf.ValueTypeNames.Asset, Sdf.ValueTypeNames.Float, Sdf.ValueTypeNames.Bool
    if t('diff'):
        sh.CreateInput('diffuse_texture', A).Set(Sdf.AssetPath(t('diff')))
    if t('nor_gl'):
        sh.CreateInput('normalmap_texture', A).Set(Sdf.AssetPath(t('nor_gl')))
    if t('rough'):
        sh.CreateInput('reflectionroughness_texture', A).Set(Sdf.AssetPath(t('rough')))
        sh.CreateInput('reflection_roughness_texture_influence', F).Set(1.0)
    if t('alpha8'):
        sh.CreateInput('enable_opacity', B).Set(True)
        sh.CreateInput('enable_opacity_texture', B).Set(True)
        sh.CreateInput('opacity_texture', A).Set(Sdf.AssetPath(t('alpha8')))
        sh.CreateInput('opacity_mode', Sdf.ValueTypeNames.Int).Set(1)
        sh.CreateInput('opacity_threshold', F).Set(0.5)
    sh.CreateInput('specular_level', F).Set(0.35)
    out = sh.CreateOutput('out', Sdf.ValueTypeNames.Token)
    for o in (mat.CreateSurfaceOutput('mdl'), mat.CreateVolumeOutput('mdl'), mat.CreateDisplacementOutput('mdl')):
        o.ConnectToSource(out)
    return mat


# (grupo, modelo, densidad por m² o n.º fijo, escala min-max, holgura al circuito (m))
DRESSING = {
    'Understory': [('understory', 'fern_02', 0.22, (1.4, 2.6), 1.0),
                   ('understory', 'calathea_orbifolia_01', 0.06, (1.5, 2.5), 1.0),
                   ('understory', 'anthurium_botany_01', 0.05, (1.2, 2.0), 1.0),
                   ('understory', 'shrub_02', 0.012, (0.7, 1.2), 1.8),
                   ('understory', 'shrub_03', 0.05, (1.5, 3.0), 1.0)],
    'Deadwood': [('deadwood', 'tree_stump_01', 10, (0.6, 1.1), 2.0),
                 ('deadwood', 'tree_stump_02', 10, (0.6, 1.1), 2.0),
                 ('deadwood', 'dead_tree_trunk', 14, (0.8, 1.5), 2.2),
                 ('deadwood', 'dead_tree_trunk_02', 6, (0.7, 1.1), 3.0),
                 ('deadwood', 'root_cluster_01', 4, (0.6, 1.0), 3.0),
                 ('deadwood', 'bark_debris_01', 0.03, (0.8, 1.5), 0.6),
                 ('deadwood', 'dry_branches_medium_01', 0.04, (0.8, 1.6), 0.8)],
    'Rocks': [('rocks', 'rock_moss_set_01', 8, (0.3, 0.8), 2.5),
              ('rocks', 'rock_moss_set_02', 10, (0.3, 0.8), 2.0),
              ('rocks', 'boulder_01', 5, (0.5, 1.0), 2.5)],
}
LABELS = {'Understory': 'understory', 'Deadwood': 'deadwood', 'Rocks': 'rock'}


def dress(stage, rng, T, tree_xy, path, args, radius=60.0):
    """Sotobosque, madera muerta y rocas en un disco de `radius` m, sin tocar troncos ni el circuito."""
    tree_xy = np.asarray(tree_xy)
    area = np.pi * radius ** 2
    counts = {}
    for group, items in DRESSING.items():
        UsdGeom.Scope.Define(stage, f'/World/{group}')
        protos_root = f'/World/{group}/All/Prototypes'
        UsdGeom.Xform.Define(stage, f'/World/{group}/All')
        UsdGeom.Scope.Define(stage, protos_root)
        all_protos, idx, xyz, yaw, scl = [], [], [], [], []
        for folder, model, dens, (s0, s1), clear in items:
            protos = DR.prototypes(stage, protos_root, folder, model, prop_material)
            if not protos:
                continue
            n = int(dens * area) if dens < 1 else int(dens)
            foot = max(float(np.max(sz[:2])) for _, sz in protos) * s1 / 2

            def ok(P, clear=clear, foot=foot):
                d_tree = np.linalg.norm(P[:, None] - tree_xy[None], axis=-1).min(1)
                return (d_tree > 0.8 + foot * 0.5) & (DR.dist_to_path(path, P) > clear + foot)
            P = DR.scatter(rng, n, radius, ok)
            base = len(all_protos)
            all_protos += protos
            idx += (base + rng.integers(len(protos), size=len(P))).tolist()
            z = DR.terrain_height(T, P[:, 0], P[:, 1]) - 0.03
            xyz += np.c_[P, z].tolist()
            yaw += rng.uniform(0, 2 * np.pi, len(P)).tolist()
            scl += rng.uniform(s0, s1, len(P)).tolist()
            counts[model] = len(P)
        DR.instancer(stage, f'/World/{group}/All', all_protos, idx, xyz, yaw, scl, LABELS[group])
    return counts


def poisson_disk(rng, n, half, min_d, tries=5000):
    out = []
    for _ in range(tries):
        p = rng.uniform(-half, half, 2)
        if all(np.hypot(*(p - q)) >= min_d for q in out):
            out.append(p)
            if len(out) == n:
                break
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default=os.path.join(HERE, '..', 'synth_trees', 'work'))
    ap.add_argument('--n-trees', type=int, default=24)
    ap.add_argument('--plot', type=float, default=60.0, help='lado de la parcela (m)')
    ap.add_argument('--min-dist', type=float, default=7.0)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', default=os.path.join(HERE, 'scenes', 'forest_v2_bosque.usd'))
    ap.add_argument('--flat', action='store_true', help='colores planos en vez de texturas y cielo HDRI')
    ap.add_argument('--hdri', default=None, help='por defecto rainforest_trail (bosque) o farmland_overcast (--bare)')
    ap.add_argument('--bare', action='store_true', help='sin ambientación: suelo plano, sin sotobosque ni anillo exterior')
    ap.add_argument('--outer-trees', type=int, default=110)
    ap.add_argument('--outer-radius', type=float, default=95.0)
    ap.add_argument('--ground', type=float, default=400.0, help='lado del suelo (m)')
    ap.add_argument('--tubes', action='store_true', help='un cilindro por segmento QSM (versión antigua)')
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    args.hdri = args.hdri or ('farmland_overcast_2k.hdr' if args.bare else 'rainforest_trail_2k.hdr')

    # mitad G2, mitad G4; fuentes distintas para no repetir el mismo árbol
    picks = []
    used = set()
    for gen in GENS:
        files = sorted(f for f in os.listdir(os.path.join(args.work, 'syn_' + gen)) if f.endswith('.npz'))
        for f in rng.permutation(files):
            src = f.split('__')[0]
            if src in used:
                continue
            used.add(src)
            picks.append((gen, os.path.join(args.work, 'syn_' + gen, f)))
            if sum(g == gen for g, _ in picks) == args.n_trees // 2:
                break
    pos = poisson_disk(rng, len(picks), args.plot / 2 - 3, args.min_dist)
    picks = picks[:len(pos)]
    dr_rng = np.random.default_rng(args.seed + 7)        # rng aparte: los 24 árboles no cambian
    T = DR.terrain_params(dr_rng) if not args.bare else dict(kx=[], ky=[], a=[], ph=[])
    loop = DR.plan_loop(pos, args.plot / 2)
    outer = []
    if not args.bare and args.outer_trees:
        pool = [(g, os.path.join(args.work, 'syn_' + g, f)) for g in GENS
                for f in sorted(os.listdir(os.path.join(args.work, 'syn_' + g)))
                if f.endswith('.npz') and f.split('__')[0] not in used]
        sel = dr_rng.choice(len(pool), args.outer_trees, replace=False)
        opos = DR.scatter(dr_rng, args.outer_trees * 3, args.outer_radius, lambda P: np.ones(len(P), bool),
                          r_min=args.plot / 2 + 4)
        keep = []
        for p in opos:                                  # separación mínima de 5 m
            if all(np.hypot(*(p - q)) >= 5.0 for q in keep):
                keep.append(p)
            if len(keep) == args.outer_trees:
                break
        outer = [(pool[i], p) for i, p in zip(sel, keep)]

    stage = Usd.Stage.CreateNew(args.out)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    world = UsdGeom.Xform.Define(stage, '/World')
    stage.SetDefaultPrim(world.GetPrim())
    mats = {k: material(stage, k, c) for k, c in COLORS.items()}
    if not args.flat:
        mats['ground'] = omnipbr(stage, '/World/Looks/ForestFloor', 'forrest_ground_01', scale=(0.25, 0.25))
        barks = [omnipbr(stage, f'/World/Looks/{b}', b, scale=(0.6, 0.6) if args.tubes else (1.0, 1.0),
                         world_project=args.tubes) for b in BARKS]

    if args.bare:
        g = args.ground / 2
        gp = np.array([[-g, -g, 0], [g, -g, 0], [g, g, 0], [-g, g, 0]], float)
        add_mesh(stage, '/World/Ground', gp, np.array([4]), np.arange(4), 'ground', mats['ground'])
    else:
        floor = omnipbr(stage, '/World/Looks/LeafLitter', 'forest_leaves_02', scale=(0.35, 0.35))
        P, C, I, N = DR.terrain_mesh(T, half=args.outer_radius + 35)
        add_mesh(stage, '/World/Ground', P, C, I, 'ground', floor, normals=N)

    meta = []
    n_faces = 0
    for k, ((gen, path), (x, y)) in enumerate(zip(picks, pos)):
        t = qsm.load_npz(path)
        yaw = rng.uniform(0, 2 * np.pi)
        R = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
        start = (t.start - t.start[0]) @ R.T + [x, y, 0]
        axis = t.axis @ R.T
        name = f'tree_{k:02d}'
        xf = UsdGeom.Xform.Define(stage, f'/World/Trees/{name}')
        bark = None if args.flat else barks[rng.integers(len(barks))]
        if args.tubes:
            for cls, sel in (('trunk', t.order == 0), ('branch', t.order >= 1)):
                if sel.any():
                    P, C, I = tube_mesh(start[sel], axis[sel], t.length[sel], t.radius[sel])
                    add_mesh(stage, f'{xf.GetPath()}/{cls}', P, C, I, cls, bark or mats[cls])
                    n_faces += len(C)
        else:
            z0 = float(DR.terrain_height(T, x, y)) - 0.15          # base algo enterrada en el terreno
            for cls, m in tree_mesh(t, R, np.array([x, y, z0])).items():
                add_mesh(stage, f'{xf.GetPath()}/{cls}', m['points'], m['counts'], m['indices'], cls,
                         bark or mats[cls], normals=m['normals'], uvs=m['uvs'])
                n_faces += len(m['counts'])
        xf.GetPrim().SetCustomDataByKey('shagai:source', t.name)
        meta.append(dict(prim=str(xf.GetPath()), tree=t.name, generator=GENS[gen], species=t.species,
                         x=float(x), y=float(y), yaw_deg=float(np.degrees(yaw)),
                         height=float(t.end[:, 2].max() - t.start[0, 2]), n_cyl=int(t.n)))

    n_outer = 0
    for k, ((gen, path_npz), (x, y)) in enumerate(outer):
        t = qsm.load_npz(path_npz)
        yaw = dr_rng.uniform(0, 2 * np.pi)
        R = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
        z0 = float(DR.terrain_height(T, x, y)) - 0.15
        xf = UsdGeom.Xform.Define(stage, f'/World/OuterTrees/outer_{k:03d}')
        bark = barks[dr_rng.integers(len(barks))]
        for cls, m in tree_mesh(t, R, np.array([x, y, z0]), lod=True).items():
            add_mesh(stage, f'{xf.GetPath()}/{cls}', m['points'], m['counts'], m['indices'], cls, bark,
                     normals=m['normals'], uvs=m['uvs'])
            n_faces += len(m['counts'])
        n_outer += 1
    props = {} if args.bare else dress(stage, dr_rng, T, pos, loop, args)

    # luz: cielo (HDRI o color) + sol
    dome = UsdLux.DomeLight.Define(stage, '/World/Sky')
    if args.flat:
        dome.CreateIntensityAttr(600)
        dome.CreateColorAttr(Gf.Vec3f(0.85, 0.9, 1.0))
    else:
        dome.CreateTextureFileAttr(Sdf.AssetPath(os.path.join(ASSETS, 'hdri', args.hdri)))
        dome.CreateTextureFormatAttr(UsdLux.Tokens.latlong)
        dome.CreateIntensityAttr(1000)
    sun = UsdLux.DistantLight.Define(stage, '/World/Sun')
    sun.CreateIntensityAttr(1500)
    sun.CreateAngleAttr(0.5)
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(35, 0, 30))
    stage.GetRootLayer().Save()
    with open(os.path.splitext(args.out)[0] + '_trees.json', 'w') as f:
        json.dump(dict(plot=args.plot, seed=args.seed, trees=meta, terrain=T, path_xy=loop[::4].tolist(),
                       outer_trees=n_outer, props=props), f, indent=1)
    if not args.bare:
        print(f'ambientación: {n_outer} árboles exteriores, objetos {props}')
    print(f'{len(meta)} árboles ({sum(m["generator"] == "G2" for m in meta)} G2 + '
          f'{sum(m["generator"] == "G4" for m in meta)} G4), {n_faces / 1e6:.2f} M caras -> {args.out}')


if __name__ == '__main__':
    main()

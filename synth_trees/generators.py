"""Generadores de árboles sintéticos a partir de QSM reales.

G0  iid_radius     línea base del repo qsm-variation: radio × U(1±frac) por cilindro.
G1  allometric     perturbación por rama: radio, longitud (ligada al radio por la
                   alometría medida) y ángulos de inserción/azimut. Magnitudes =
                   alpha × variabilidad natural medida en train.
G2  recombine      sustituye ramas de orden 1 por ramas de orden 1 de otros árboles
                   de la misma especie (train), reescaladas con la alometría.
G3  hybrid         G2 + G1 suave.
G4  procedural     árbol nuevo desde cero: tronco con el tamaño del fuente y copa
                   construida rama a rama sorteando reglas de ramas reales de la especie.

Todos los parámetros estadísticos salen de ``fit_stats`` (solo árboles de train).
"""
import numpy as np
import pandas as pd

import qsm


# ------------------------------------------------------------------ estadísticos

def fit_stats(trees, branches):
    """Alometrías y dispersiones naturales a partir de las tablas de train."""
    tr = trees[trees.split == 'train']
    br = branches[branches.split == 'train']
    # árbol: log altura ~ log DBH
    b_tree, a_tree = np.polyfit(np.log(tr.dbh), np.log(tr.height), 1)
    res_h = np.log(tr.height) - (a_tree + b_tree * np.log(tr.dbh))
    # dispersión de tamaño dentro de especie (especies con ≥3 árboles)
    g = tr.groupby('species').dbh
    sd_logd = np.sqrt(np.nanmean(g.apply(lambda x: np.var(np.log(x), ddof=1) if len(x) >= 3 else np.nan)))
    # rama: log longitud ~ log radio
    ok = (br.length > 0) & (br.radius > 0)
    b_br, a_br = np.polyfit(np.log(br.radius[ok]), np.log(br.length[ok]), 1)
    res_l = np.log(br.length[ok]) - (a_br + b_br * np.log(br.radius[ok]))
    # dispersión del cociente de diámetros y del ángulo, por orden
    sd_ratio, sd_angle = {}, {}
    for o, gb in br.groupby('order'):
        if len(gb) < 30:
            continue
        sd_ratio[o] = np.std(np.log(gb.diam_ratio.clip(1e-3)), ddof=1)
        sd_angle[o] = np.std(gb.insert_angle, ddof=1)
    return dict(b_tree=b_tree, sd_res_h=np.std(res_h, ddof=1), sd_logd=sd_logd,
                b_br=b_br, sd_res_l=np.std(res_l, ddof=1),
                sd_ratio=sd_ratio, sd_angle=sd_angle)


def _get(d, o):
    return d[o] if o in d else d[max(d)]


# ------------------------------------------------------------------ utilidades

def _branch_first(t):
    """Índice del primer cilindro de cada rama."""
    first = np.zeros(t.branch.max() + 1, np.int64)
    idx = np.where(t.pos == 1)[0]
    first[t.branch[idx]] = idx
    return first


def _sph(a):
    """Vector local -> (theta, phi) respecto al eje z del marco del padre."""
    return np.arccos(np.clip(a[2], -1, 1)), np.arctan2(a[1], a[0])


def _unsph(th, ph):
    return np.array([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])


def _subtree(children, root):
    out, stack = [], [root]
    while stack:
        i = stack.pop()
        out.append(i)
        stack.extend(children[i])
    return sorted(out)


# ------------------------------------------------------------------ G0

def iid_radius(t, rng, frac=0.10):
    s = t.copy()
    s.radius = s.radius * rng.uniform(1 - frac, 1 + frac, s.n)
    return s


# ------------------------------------------------------------------ G1

def allometric(t, rng, st, alpha=0.5, max_angle=150.0):
    L = qsm.encode(t)
    # tamaño global siguiendo altura ~ DBH
    lf = alpha * st['sd_logd'] * rng.standard_normal()
    L.radius *= np.exp(lf)
    L.length *= np.exp(st['b_tree'] * lf + alpha * st['sd_res_h'] * rng.standard_normal())
    first = _branch_first(t)
    for b in range(1, len(first)):        # ramas en orden topológico (el padre aparece antes)
        i = first[b]
        o = int(t.order[i])
        cyl = t.branch == b
        # factores log-normales con media 1 (sin la corrección, las ramas crecen en promedio)
        sr = alpha * _get(st['sd_ratio'], o)
        sl = alpha * st['sd_res_l']
        rf = sr * rng.standard_normal() - sr ** 2 / 2
        lfb = st['b_br'] * (rf + sr ** 2 / 2) + sl * rng.standard_normal() \
            - ((st['b_br'] * sr) ** 2 + sl ** 2) / 2
        L.radius[cyl] *= np.exp(rf)
        L.length[cyl] *= np.exp(lfb)
        # la rama no puede ser más gruesa que el padre (si en el original no lo era)
        p = t.parent[i]
        lim = L.radius[p] * max(1.0, t.radius[i] / t.radius[p])
        if L.radius[i] > lim:
            L.radius[cyl] *= lim / L.radius[i]
        th, ph = _sph(L.aloc[i])
        sa = np.radians(alpha * _get(st['sd_angle'], o))
        th = np.clip(th + sa * rng.standard_normal(), np.radians(2), np.radians(max_angle))
        ph = ph + sa * rng.standard_normal()
        L.aloc[i] = _unsph(th, ph)
    return qsm.decode(L, t.name, t.species)


# ------------------------------------------------------------------ G2

class DonorPool:
    """Ramas de orden 1 de los árboles de train, ya codificadas en local."""

    def __init__(self, trees):
        self.items = []
        for t in trees:
            L = qsm.encode(t)
            ch = t.children()
            first = _branch_first(t)
            base_z = t.start[0, 2]
            height = t.end[:, 2].max() - base_z
            for b in range(1, len(first)):
                i = first[b]
                if t.order[i] != 1:
                    continue
                sub = _subtree(ch, i)
                self.items.append(dict(
                    tree=t.name, species=t.species, root=i, idx=np.array(sub),
                    radius=t.radius[i], rel_h=(t.start[i, 2] - base_z) / height,
                    L=L))
        self.df = pd.DataFrame([{k: v for k, v in d.items() if k in ('tree', 'species', 'radius', 'rel_h')}
                                for d in self.items])


def recombine(t, rng, pool, st, p_swap=0.5, topk=5, max_dh=0.15, max_logr=np.log(2)):
    L = qsm.encode(t)
    ch = t.children()
    first = _branch_first(t)
    base_z = t.start[0, 2]
    height = t.end[:, 2].max() - base_z
    cand = pool.df[(pool.df.species == t.species) & (pool.df.tree != t.name)]
    cross = False
    if cand.empty:
        cand = pool.df[pool.df.tree != t.name]
        cross = True
    keep = np.ones(t.n, bool)
    grafts = []          # (padre en t, tuv, aloc objetivo, item donante, escala radio)
    for b in range(1, len(first)):
        i = first[b]
        if t.order[i] != 1 or rng.random() > p_swap:
            continue
        rel_h = (t.start[i, 2] - base_z) / height
        dlr = np.abs(np.log(cand.radius / t.radius[i]))
        dh = np.abs(cand.rel_h - rel_h)
        ok = cand[(dh < max_dh) & (dlr < max_logr)]
        if ok.empty:
            continue
        score = dh[ok.index] / max_dh + dlr[ok.index] / max_logr
        pick = ok.loc[score.nsmallest(topk).index]
        item = pool.items[int(rng.choice(pick.index))]
        keep[_subtree(ch, i)] = False
        th_d, _ = _sph(item['L'].aloc[item['root']])
        _, ph_t = _sph(L.aloc[i])
        grafts.append((t.parent[i], L.tuv[i].copy(), _unsph(th_d, ph_t), item,
                       t.radius[i] / item['radius']))
    # árbol objetivo sin las ramas sustituidas
    kept = np.where(keep)[0]
    remap = -np.ones(t.n, np.int64)
    remap[kept] = np.arange(len(kept))
    parts = dict(tuv=[L.tuv[kept]], aloc=[L.aloc[kept]], length=[L.length[kept]],
                 radius=[L.radius[kept]],
                 parent=[np.where(L.parent[kept] >= 0, remap[np.maximum(L.parent[kept], 0)], -1)],
                 ext=[np.where(L.ext[kept] >= 0, remap[np.maximum(L.ext[kept], 0)], -1)])
    n = len(kept)
    donors = []
    for p, tuv, aloc, item, k in grafts:
        D, idx = item['L'], item['idx']
        rmap = -np.ones(len(D.length), np.int64)
        rmap[idx] = np.arange(len(idx)) + n
        par = np.where(D.parent[idx] >= 0, rmap[np.maximum(D.parent[idx], 0)], -1)
        par[0] = remap[p]
        ext = np.where(D.ext[idx] >= 0, rmap[np.maximum(D.ext[idx], 0)], -1)
        tv, al = D.tuv[idx].copy(), D.aloc[idx].copy()
        tv[0], al[0] = tuv, aloc
        parts['tuv'].append(tv)
        parts['aloc'].append(al)
        parts['radius'].append(D.radius[idx] * k)
        parts['length'].append(D.length[idx] * k ** st['b_br'])
        parts['parent'].append(par)
        parts['ext'].append(ext)
        donors.append(item['tree'])
        n += len(idx)
    NL = qsm.Local(L.root_start, L.root_frame, *(np.concatenate(parts[k]) for k in
                                                  ('tuv', 'aloc', 'length', 'radius', 'parent', 'ext')))
    s = qsm.decode(NL, t.name, t.species)
    s.meta.update(n_swapped=len(grafts), donors=sorted(set(donors)), cross_species=cross)
    return s


# ------------------------------------------------------------------ G3

def hybrid(t, rng, pool, st, p_swap=0.5, alpha=0.25, **kw):
    """G2 seguido de G1 suave: ramas de otros árboles y además variación de cada rama."""
    s = recombine(t, rng, pool, st, p_swap=p_swap, **kw)
    out = allometric(s, rng, st, alpha=alpha)
    out.meta.update(s.meta)
    return out


# ------------------------------------------------------------------ G4

S_GRID = np.linspace(0, 1, 11)       # posiciones normalizadas a lo largo de una rama


def _path(t, idx):
    """Longitud acumulada al inicio de cada cilindro de la lista idx (ordenada por pos)."""
    return np.r_[0, np.cumsum(t.length[idx])[:-1]]


def _zen(a):
    return np.degrees(np.arccos(np.clip(a[..., 2], -1, 1)))


def branch_rows(t):
    """Reglas de cada rama real: dónde nace, grosor, ángulos, curvatura, adelgazamiento...

    Una fila = una rama. G4 construye ramas nuevas sorteando filas completas, así
    conserva las correlaciones entre rasgos de una misma rama.
    """
    nb = t.branch.max() + 1
    cyl = [[] for _ in range(nb)]
    for i in np.lexsort((t.pos, t.branch)):
        cyl[t.branch[i]].append(i)
    cum = np.zeros(t.n)
    blen = np.zeros(nb)
    for b, idx in enumerate(cyl):
        cum[idx] = _path(t, idx)
        blen[b] = t.length[idx].sum()
    nchild = np.bincount(t.branch[t.parent[[c[0] for c in cyl[1:]]]], minlength=nb)
    rows = []
    for b, idx in enumerate(cyl):
        idx = np.array(idx)
        L = blen[b]
        mid = (cum[idx] + t.length[idx] / 2) / L
        prof = np.interp(S_GRID, mid, t.radius[idx]) / t.radius[idx[0]]
        # dirección final: media de los cilindros del último 30 % de la rama
        tail = idx[cum[idx] + t.length[idx] > 0.7 * L]
        dend = (t.axis[tail] * t.length[tail, None]).sum(0)
        joints = np.degrees(np.arccos(np.clip(np.sum(t.axis[idx[1:]] * t.axis[idx[:-1]], 1), -1, 1)))
        r = dict(order=int(t.order[idx[0]]), radius=t.radius[idx[0]], length=L,
                 zen0=_zen(t.axis[idx[0]]), zen1=_zen(dend / np.linalg.norm(dend)),
                 wiggle=np.sqrt(np.mean(joints ** 2)) if len(joints) else 0.0,
                 seg=np.median(t.length[idx]), n_children=int(nchild[b]),
                 child_density=nchild[b] / L, prof=prof)
        p = t.parent[idx[0]]
        if p >= 0:
            along = np.clip(np.dot(t.start[idx[0]] - t.start[p], t.axis[p]), 0, t.length[p])
            r.update(rel_pos=(cum[p] + along) / blen[t.branch[p]],
                     length_ratio=L / blen[t.branch[p]],
                     diam_ratio=t.radius[idx[0]] / t.radius[p],
                     insert_angle=np.degrees(np.arccos(np.clip(np.dot(t.axis[idx[0]], t.axis[p]), -1, 1))))
        rows.append(r)
    return rows


class ProcRules:
    """Reglas empíricas (solo train) para el generador procedural G4."""

    def __init__(self, trees):
        trunks, rows = {}, []
        for t in trees:
            rr = branch_rows(t)
            trunks[t.name] = rr[0]
            for r in rr[1:]:
                r.update(tree=t.name, species=t.species)
                rows.append(r)
        self.trunks = trunks
        self.prof = np.array([r.pop('prof') for r in rows])
        df = pd.DataFrame(rows)
        # alometría longitud ~ radio por orden; cada fila guarda su residuo
        self.allo = {}
        df['len_res'] = 0.0
        for o, g in df.groupby('order'):
            if len(g) < 30:
                continue
            b, a = np.polyfit(np.log(g.radius), np.log(g.length), 1)
            self.allo[o] = (a, b)
            df.loc[g.index, 'len_res'] = np.log(g.length) - (a + b * np.log(g.radius))
        self.df = df
        self.parent_r = (df.radius / df.diam_ratio).values
        self.r_min = np.quantile(df.radius, 0.01)
        self.max_order = max(self.allo)
        self._by = {k: g.index.values for k, g in df.groupby(['species', 'order'])}
        self._by_o = {o: g.index.values for o, g in df.groupby('order')}

    def candidates(self, species, order, exclude_tree, min_n=20):
        idx = self._by.get((species, order), np.array([], int))
        own = self.df.tree.values[idx] == exclude_tree
        if (~own).sum() >= min_n:
            return idx[~own]
        return self._by_o.get(order, np.array([], int))


def _turn(d, axis_from, deg, rng, target_zen=None):
    """Dirección a `deg` grados de axis_from; el azimut se elige para acercarse a target_zen."""
    a = axis_from / np.linalg.norm(axis_from)
    F = qsm._root_frame(a)
    u, v = F[:, 0], F[:, 1]
    th = np.radians(deg)
    R = np.sin(th) * np.hypot(u[2], v[2])
    if target_zen is None or R < 1e-6:
        ph = rng.uniform(0, 2 * np.pi)
    else:
        ph0 = np.arctan2(v[2], u[2])
        c = (np.cos(np.radians(target_zen)) - np.cos(th) * a[2]) / R
        ph = ph0 + rng.choice([-1, 1]) * np.arccos(np.clip(c, -1, 1))
    return np.cos(th) * a + np.sin(th) * (np.cos(ph) * u + np.sin(ph) * v)


def _with_zenith(d, zen):
    """Misma dirección horizontal que d, con cenit `zen` (grados)."""
    h = np.array([d[0], d[1], 0.0])
    h = h / np.linalg.norm(h) if np.linalg.norm(h) > 1e-9 else np.array([1.0, 0, 0])
    z = np.radians(zen)
    return np.sin(z) * h + np.cos(z) * np.array([0, 0, 1.0])


def _slerp(a, b, s):
    c = np.clip(np.dot(a, b), -1, 1)
    w = np.arccos(c)
    if w < 1e-6:
        return a
    return (np.sin((1 - s) * w) * a + np.sin(s * w) * b) / np.sin(w)


def procedural(t, rng, rules, st, size_alpha=0.5, wiggle_k=1.0, n_try=32, topk=3,
               max_cyl_factor=4.0):
    """Árbol nuevo desde cero con las reglas de la especie (Stava-style, sin ajuste inverso).

    Del árbol fuente solo se toman la especie, el tamaño del tronco (con variación),
    su perfil de adelgazamiento y su número de ramas principales. Toda la copa se
    construye sorteando reglas de ramas reales de otros árboles de la misma especie.
    """
    tr = rules.trunks[t.name]
    k = np.exp(size_alpha * st['sd_logd'] * rng.standard_normal())
    trunk_len = tr['length'] * k ** st['b_tree']
    r_base = t.radius[0] * k
    S = dict(start=[], axis=[], length=[], radius=[], parent=[], cont=[])
    max_cyl = int(max_cyl_factor * t.n)

    def build(p_cyl, p0, d0, d1, L, r0, prof, seg, wig):
        """Añade una rama como polilínea; devuelve índices, inicio acumulado y radios."""
        n = max(1, int(round(L / max(seg, 0.02))))
        h = L / n
        first = len(S['radius'])
        x = np.array(p0, float)
        ids, cums = [], []
        for j in range(n):
            s = (j + 0.5) / n
            d = _slerp(d0, d1, j / max(n - 1, 1))
            if j > 0 and wig > 0:
                d = _turn(None, d, abs(wig * rng.standard_normal()), rng)
            d /= np.linalg.norm(d)
            S['start'].append(x.copy())
            S['axis'].append(d)
            S['length'].append(h)
            S['radius'].append(max(r0 * np.interp(s, S_GRID, prof), rules.r_min / 2))
            S['parent'].append(p_cyl if j == 0 else first + j - 1)
            S['cont'].append(j > 0)
            ids.append(first + j)
            cums.append(j * h)
            x = x + d * h
        return np.array(ids), np.array(cums)

    # tronco: dirección inicial y final con el cenit real del fuente pero azimut nuevo
    az = rng.uniform(0, 2 * np.pi, 2)
    d0 = _with_zenith(np.array([np.cos(az[0]), np.sin(az[0]), 0]), tr['zen0'])
    d1 = _with_zenith(np.array([np.cos(az[1]), np.sin(az[1]), 0]), tr['zen1'])
    ids, cums = build(-1, t.start[0], d0, d1, trunk_len, r_base, tr['prof'], tr['seg'],
                      wiggle_k * tr['wiggle'])
    queue = [(ids, cums, trunk_len, 0, rng.poisson(tr['n_children']))]
    n_grown = 0
    while queue and len(S['radius']) < max_cyl:
        ids, cums, L, order, n_ch = queue.pop(0)
        o = order + 1
        if o > rules.max_order:
            continue
        cand = rules.candidates(t.species, o, t.name)
        if len(cand) == 0:
            continue
        rad = np.array(S['radius'])[ids]
        for _ in range(n_ch):
            # entre unas cuantas reglas al azar, una cuyo padre real tenía un grosor parecido
            sub = rng.choice(cand, min(n_try, len(cand)), replace=False)
            js = np.minimum(np.searchsorted(cums, rules.df.rel_pos.values[sub] * L, side='right') - 1,
                            len(ids) - 1)
            err = np.abs(np.log(rad[js] / rules.parent_r[sub]))
            ri = sub[rng.choice(np.argsort(err)[:topk])]
            row = rules.df.loc[ri]
            pos = row.rel_pos * L
            j = min(np.searchsorted(cums, pos, side='right') - 1, len(ids) - 1)
            pc = ids[j]
            r0 = row.diam_ratio * S['radius'][pc]
            if r0 < rules.r_min:
                continue
            a, b = rules.allo.get(o, rules.allo[rules.max_order])
            Lc = np.exp(a + b * np.log(r0) + row.len_res)
            p0 = S['start'][pc] + S['axis'][pc] * (pos - cums[j])
            dc0 = _turn(None, S['axis'][pc], row.insert_angle, rng, target_zen=row.zen0)
            dc1 = _with_zenith(dc0, row.zen1)
            cids, ccums = build(pc, p0, dc0, dc1, Lc, r0, rules.prof[ri], row.seg,
                                wiggle_k * row.wiggle)
            # número de hijas de la rama real, corregido por el cambio de longitud
            m = row.n_children * Lc / row.length
            queue.append((cids, ccums, Lc, o, int(m) + (rng.random() < m % 1)))
            n_grown += 1
    n = len(S['radius'])
    parent = np.array(S['parent'], np.int64)
    ext = -np.ones(n, np.int64)
    cont = np.array(S['cont'])
    ext[parent[cont]] = np.where(cont)[0]
    s = qsm.Tree(np.array(S['start']), np.array(S['axis']), np.array(S['length']),
                 np.array(S['radius']), parent, ext, t.name, t.species).recompute_topology()
    s.meta.update(n_grown=n_grown, size_k=round(float(k), 3), capped=bool(len(queue)))
    return s


# ------------------------------------------------------------------ G5 (grupo 1: reglas)

GOLDEN = np.radians(137.5)      # ángulo de filotaxis


def pipe_exponent(trees, min_r=0.02):
    """Exponente Δ de Leonardo (r_padre^Δ = Σ r_hijas^Δ), mediana por bifurcación."""
    from scipy.optimize import brentq
    out = []
    for t in trees:
        for p, c in enumerate(t.children()):
            if len(c) < 2 or t.radius[p] < min_r:
                continue
            q = t.radius[c] / t.radius[p]
            try:
                out.append(brentq(lambda d: np.sum(q ** d) - 1, 0.5, 12))
            except ValueError:
                pass
    return float(np.median(out))


class RuleSet:
    """Reglas botánicas resumidas en pocos números por especie y orden (solo train).

    A diferencia de G4, no se copian ramas reales: cada regla es una media y una
    dispersión (distribución normal o log-normal) y las ramas se generan con ellas.
    """

    def __init__(self, trees, tree_table, rules):
        self.delta = pipe_exponent(trees)
        df = rules.df
        tr = tree_table[tree_table.split == 'train'].copy()
        tr['trunk_frac'] = tr.trunk_height / tr.height
        tr['o1_per_m'] = tr.n_br_o1 / (tr.trunk_height * (1 - tr.crown_base_rel.fillna(0.5)))
        self.allo = rules.allo
        self.sd_res = df.groupby('order').len_res.std().to_dict()
        self.r_min = rules.r_min
        self.max_order = rules.max_order
        self.seg = df.groupby('order').seg.median().to_dict()

        def summ(g):
            return dict(n=len(g),
                        q_mu=np.log(g.diam_ratio.clip(1e-3, 1)).mean(),
                        q_sd=np.log(g.diam_ratio.clip(1e-3, 1)).std(),
                        ang_mu=g.insert_angle.mean(), ang_sd=g.insert_angle.std(),
                        zen1_mu=g.zen1.mean(), zen1_sd=g.zen1.std(),
                        dens_mu=g.child_density[g.length > 0.5].mean(),
                        pos_lo=g.rel_pos.quantile(0.1),
                        lr_max=g.length_ratio.quantile(0.95),
                        wig=g.wiggle.median())
        self.by_o = {o: summ(g) for o, g in df.groupby('order')}
        self.by_so = {k: summ(g) for k, g in df.groupby(['species', 'order']) if len(g) >= 30}
        tr_t = {k: rules.trunks[n] for k, n in zip(tr.tree, tr.tree)}
        tr['seg0'] = [tr_t[n]['seg'] for n in tr.tree]
        tr['wig0'] = [tr_t[n]['wiggle'] for n in tr.tree]
        cols = ['trunk_frac', 'crown_base_rel', 'o1_per_m', 'seg0', 'wig0']
        prof = pd.DataFrame(rules.prof)
        prof['species'], prof['order'] = df.species.values, df.order.values
        self.prof_o = prof.groupby('order')[list(range(len(S_GRID)))].median()
        self.prof_so = {k: g[list(range(len(S_GRID)))].median().values
                        for k, g in prof.groupby(['species', 'order']) if len(g) >= 30}
        tp = pd.DataFrame([rules.trunks[n]['prof'] for n in tr.tree])
        tp['species'] = tr.species.values
        self.prof_trunk_all = tp.drop(columns='species').median().values
        self.prof_trunk = tp.groupby('species').median().T.to_dict('list')
        self.tree_all = tr[cols].median().to_dict()
        self.tree_sp = tr.groupby('species')[cols].median().to_dict('index')
        # altura ~ DBH con intercepto propio de cada especie (pendiente común)
        b = np.polyfit(np.log(tr.dbh), np.log(tr.height), 1)[0]
        self.h_b = b
        self.h_a = (np.log(tr.height) - b * np.log(tr.dbh)).groupby(tr.species).mean().to_dict()
        self.h_a_all = float(np.mean(np.log(tr.height) - b * np.log(tr.dbh)))

    def prof(self, species, o):
        if o == 0:
            return np.array(self.prof_trunk.get(species, self.prof_trunk_all))
        return self.prof_so.get((species, o), self.prof_o.loc[min(o, self.prof_o.index.max())].values)

    def br(self, species, o):
        return self.by_so.get((species, o), self.by_o.get(o, self.by_o[max(self.by_o)]))


class _Cyl:
    """Acumulador de cilindros para los generadores que construyen desde cero."""

    def __init__(self):
        self.start, self.axis, self.length, self.radius, self.parent, self.cont = ([] for _ in range(6))

    def axis_(self, p_cyl, p0, d0, d1, L, rfun, seg, wig, rng):
        n = max(1, int(round(L / max(seg, 0.02))))
        h = L / n
        first = len(self.radius)
        x = np.array(p0, float)
        for j in range(n):
            d = _slerp(d0, d1, j / max(n - 1, 1))
            if j > 0 and wig > 0:
                d = _turn(None, d, abs(wig * rng.standard_normal()), rng)
            d = d / np.linalg.norm(d)
            self.start.append(x.copy())
            self.axis.append(d)
            self.length.append(h)
            self.radius.append(rfun((j + 0.5) * h))
            self.parent.append(p_cyl if j == 0 else first + j - 1)
            self.cont.append(j > 0)
            x = x + d * h
        return first, n, h

    def tree(self, name, species):
        n = len(self.radius)
        parent = np.array(self.parent, np.int64)
        ext = -np.ones(n, np.int64)
        cont = np.array(self.cont)
        ext[parent[cont]] = np.where(cont)[0]
        return qsm.Tree(np.array(self.start), np.array(self.axis), np.array(self.length),
                        np.array(self.radius), parent, ext, name, species).recompute_topology()


def rule_based(t, rng, rs, st, size_alpha=0.5, max_cyl_factor=4.0):
    """Árbol desde cero solo con reglas: alometrías, perfil de adelgazamiento medio,
    filotaxis, ángulos y gravitropismo medios por especie y orden.
    Del fuente: especie y DBH (con variación)."""
    sp = t.species
    T = rs.tree_sp.get(sp, rs.tree_all)
    k = np.exp(size_alpha * st['sd_logd'] * rng.standard_normal())
    r_base = t.radius[0] * k
    dbh = 2 * r_base
    H = np.exp(rs.h_a.get(sp, rs.h_a_all) + rs.h_b * np.log(dbh) + 0.5 * st['sd_res_h'] * rng.standard_normal())
    trunk_len = H * T['trunk_frac']
    cb = T['crown_base_rel'] if np.isfinite(T['crown_base_rel']) else 0.5
    C = _Cyl()
    max_cyl = int(max_cyl_factor * t.n)
    queue = []

    def laterals(o_child, L, lo, dens):
        n = rng.poisson(max(dens, 0) * L * (1 - lo))
        pos = np.sort(rng.uniform(lo * L, L, n))
        P = rs.br(sp, o_child)
        q = np.exp(np.clip(P['q_mu'] + P['q_sd'] * rng.standard_normal(n), -6, np.log(0.95)))
        return pos, q

    def grow(p_cyl, p0, d0, d1, L, r0, o, seg, wig, pos, q):
        prof = rs.prof(sp, o)
        rfun = lambda x: max(r0 * np.interp(x / L, S_GRID, prof), rs.r_min * 0.5)
        first, n, h = C.axis_(p_cyl, p0, d0, d1, L, rfun, seg, wig, rng)
        az0 = rng.uniform(0, 2 * np.pi)
        for m, (x, qi) in enumerate(zip(pos, q)):
            j = min(int(x / h), n - 1)
            r = qi * C.radius[first + j]
            if r < rs.r_min or o + 1 > rs.max_order:
                continue
            queue.append((first + j, C.start[first + j] + C.axis[first + j] * (x - j * h), r, o + 1,
                          az0 + m * GOLDEN, L))

    # tronco: casi vertical, ramas de orden 1 solo por encima de la base de copa
    d0 = np.array([0, 0, 1.0])
    d1 = _with_zenith(rng.standard_normal(3), abs(5 * rng.standard_normal()))
    pos, q = laterals(1, trunk_len, cb, T['o1_per_m'])
    grow(-1, t.start[0], d0, d1, trunk_len, r_base, 0, T['seg0'], T['wig0'], pos, q)
    while queue and len(C.radius) < max_cyl:
        pc, p0, r0, o, az, Lp = queue.pop(0)
        P = rs.br(sp, o)
        a, b = rs.allo.get(o, rs.allo[rs.max_order])
        L = np.exp(a + b * np.log(r0) + rs.sd_res.get(o, 0.8) * rng.standard_normal())
        ang = np.clip(P['ang_mu'] + P['ang_sd'] * rng.standard_normal(), 5, 150)
        pa = C.axis[pc]
        F = qsm._root_frame(pa)
        th = np.radians(ang)
        dc0 = np.cos(th) * pa + np.sin(th) * (np.cos(az) * F[:, 0] + np.sin(az) * F[:, 1])
        dc1 = _with_zenith(dc0, np.clip(P['zen1_mu'] + P['zen1_sd'] * rng.standard_normal(), 0, 180))
        Pc = rs.br(sp, o + 1) if o + 1 in rs.by_o else P
        L = min(L, P['lr_max'] * Lp)             # una hija no supera ~el largo de su madre
        pos, q = laterals(o + 1, L, Pc['pos_lo'], P['dens_mu'])
        grow(pc, p0, dc0, dc1, L, r0, o, rs.seg.get(o, 0.1), P['wig'], pos, q)
    s = C.tree(t.name, sp)
    s.meta.update(size_k=round(float(k), 3), height_rule=round(float(H), 2), capped=bool(queue))
    return s


# ------------------------------------------------------------------ G6 (grupo 2: algoritmo)

def space_colonization(t, rng, rs, st, size_alpha=0.5, D=0.25, di_k=3.0, dk=0.5, tropism=0.15,
                       pts_per_m=1.0, max_iter=600):
    """Space colonization (Runions et al. 2007) dentro de una copa elipsoidal.

    Envolvente (altura, base y diámetro de copa) y longitud total objetivo: las del
    árbol fuente con variación de tamaño. Radios: modelo de tubería con el Δ medido.
    """
    from scipy.spatial import cKDTree
    k = np.exp(size_alpha * st['sd_logd'] * rng.standard_normal())
    tt = t.meta.get('traits') or {}
    H = tt['height'] * k ** st['b_tree']
    zb = H * (tt['crown_base_rel'] if np.isfinite(tt['crown_base_rel']) else 0.5)
    Rc = tt['crown_diam'] / 2 * k ** st['b_tree']
    n_pts = int(pts_per_m * tt['len_total'] * k ** (1 + st['b_tree']))
    # puntos de atracción uniformes en el elipsoide de copa
    c = np.array([0, 0, (zb + H) / 2])
    ax = np.array([Rc, Rc, (H - zb) / 2])
    P = rng.uniform(-1, 1, (n_pts * 3, 3))
    P = P[np.linalg.norm(P, axis=1) <= 1][:n_pts] * ax + c
    base = t.start[0]
    P += base
    # tronco inicial hasta la base de copa
    nodes = [base.copy()]
    par = [-1]
    lean = _with_zenith(rng.standard_normal(3), abs(3 * rng.standard_normal()))
    while nodes[-1][2] - base[2] < zb:
        nodes.append(nodes[-1] + D * lean)
        par.append(len(nodes) - 2)
    # radio de influencia: di_k veces la separación media entre puntos de atracción
    di = di_k * (np.prod(ax) * 4 / 3 * np.pi / max(len(P), 1)) ** (1 / 3)
    alive = np.ones(len(P), bool)
    up = np.array([0, 0, 1.0])
    for _ in range(max_iter):
        if not alive.any():
            break
        N = np.array(nodes)
        dist, near = cKDTree(N).query(P[alive], distance_upper_bound=di)
        ok = np.isfinite(dist)
        if not ok.any():
            break
        Pa, nr = P[alive][ok], near[ok]
        v = Pa - N[nr]
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        acc = np.zeros_like(N)
        np.add.at(acc, nr, v)
        grow = np.unique(nr)
        cand = np.array([N[i] + D * (lambda d: d / np.linalg.norm(d))(acc[i] / np.linalg.norm(acc[i]) + tropism * up)
                         for i in grow])
        # no brotar donde ya hay un nodo (evita ramas duplicadas)
        free = ~np.isfinite(cKDTree(N).query(cand, distance_upper_bound=0.4 * D)[0])
        if not free.any():
            break
        nodes.extend(cand[free])
        par.extend(grow[free])
        new = cand[free]
        idx_alive = np.where(alive)[0]
        hit = cKDTree(new).query(P[idx_alive], distance_upper_bound=dk)[0]
        alive[idx_alive[np.isfinite(hit)]] = False
    N = np.array(nodes)
    par = np.array(par)
    n = len(N)
    # tubería: peso = nº de puntas por debajo; r = r_tip · peso^(1/Δ), ajustado al DBH
    w = np.zeros(n)
    nchild = np.bincount(par[1:], minlength=n)
    w[nchild == 0] = 1
    for i in range(n - 1, 0, -1):
        w[par[i]] += w[i]
    r_node = (t.radius[0] * k) * (w / w[0]) ** (1 / rs.delta)
    # cilindro j = segmento del nodo j+1 a su padre; continuación = hijo más grueso
    seg_par = par[1:] - 1
    vec = N[1:] - N[par[1:]]
    L = np.linalg.norm(vec, axis=1)
    ext = -np.ones(n - 1, np.int64)
    best = {}
    for j in range(n - 1):
        p = seg_par[j]
        if p >= 0 and (p not in best or w[j + 1] > w[best[p] + 1]):
            best[p] = j
    for p, j in best.items():
        ext[p] = j
    s = qsm.Tree(N[par[1:]], vec / L[:, None], L, np.maximum(r_node[1:], rs.r_min * 0.5),
                 np.where(seg_par >= 0, seg_par, -1), ext, t.name, t.species).recompute_topology()
    s.meta.update(size_k=round(float(k), 3), n_pts=n_pts, di=round(float(di), 2), left=int(alive.sum()))
    return s

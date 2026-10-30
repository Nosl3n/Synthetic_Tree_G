"""Representación de un árbol QSM (tabla de cilindros) y codificación local.

Cada cilindro i tiene start (3,), axis (3,) unitario, length, radius y parent
(índice 0-based, -1 = raíz). ``ext[i]`` es el hijo que continúa la misma rama
(-1 si no hay). Ramas, órdenes y posiciones se recalculan siempre desde
parent/ext, de modo que reales y sintéticos pasan por el mismo código.

La codificación local expresa cada cilindro en el marco de su padre (como una
tortuga de L-system): posición relativa a lo largo del padre (t), desplazamiento
radial normalizado por el radio del padre (u, v) y eje en coordenadas del padre.
Así se pueden cambiar longitudes, radios y ángulos, o injertar subárboles, y las
uniones se reconstruyen solas.
"""
from dataclasses import dataclass, field
import os

import numpy as np
import scipy.io as sio


@dataclass
class Tree:
    start: np.ndarray
    axis: np.ndarray
    length: np.ndarray
    radius: np.ndarray
    parent: np.ndarray
    ext: np.ndarray
    name: str = ''
    species: str = ''
    meta: dict = field(default_factory=dict)
    # derivados (recompute_topology)
    branch: np.ndarray = None
    order: np.ndarray = None
    pos: np.ndarray = None

    @property
    def n(self):
        return len(self.radius)

    @property
    def end(self):
        return self.start + self.axis * self.length[:, None]

    def copy(self):
        t = Tree(self.start.copy(), self.axis.copy(), self.length.copy(),
                 self.radius.copy(), self.parent.copy(), self.ext.copy(),
                 self.name, self.species, dict(self.meta))
        return t.recompute_topology()

    def children(self):
        ch = [[] for _ in range(self.n)]
        for i, p in enumerate(self.parent):
            if p >= 0:
                ch[p].append(i)
        return ch

    def recompute_topology(self):
        """Ramas/orden/posición desde parent+ext. Exige parent[i] < i."""
        n = self.n
        branch = np.zeros(n, np.int32)
        order = np.zeros(n, np.int16)
        pos = np.ones(n, np.int32)
        nb = 0
        for i in range(n):
            p = self.parent[i]
            if p < 0:
                branch[i], order[i], pos[i] = nb, 0, 1
                nb += 1
            elif self.ext[p] == i:
                branch[i], order[i], pos[i] = branch[p], order[p], pos[p] + 1
            else:
                branch[i], order[i], pos[i] = nb, order[p] + 1, 1
                nb += 1
        self.branch, self.order, self.pos = branch, order, pos
        return self


def species_of(name):
    return name.split('_', 1)[0]


def load_mat(path):
    """Carga un .mat de TreeQSM y deja solo la parte conectada al cilindro 0."""
    d = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    c = d['QSM'].cylinder if 'QSM' in d else d['cylinder']
    parent = c.parent.astype(np.int64) - 1
    ext = c.extension.astype(np.int64) - 1
    name = os.path.splitext(os.path.basename(path))[0]
    t = Tree(np.asarray(c.start, float), np.asarray(c.axis, float),
             np.asarray(c.length, float), np.asarray(c.radius, float),
             parent, ext, name, species_of(name))
    return subset(t, reachable(t, 0))


def reachable(t, root):
    ch = t.children()
    keep, stack = [], [root]
    while stack:
        i = stack.pop()
        keep.append(i)
        stack.extend(ch[i])
    return np.array(sorted(keep))


def subset(t, idx):
    """Árbol con los cilindros idx (ordenados; el primero pasa a ser la raíz)."""
    idx = np.asarray(idx)
    remap = -np.ones(t.n, np.int64)
    remap[idx] = np.arange(len(idx))
    par = np.where(t.parent[idx] >= 0, remap[np.maximum(t.parent[idx], 0)], -1)
    par[0] = -1
    ext = np.where(t.ext[idx] >= 0, remap[np.maximum(t.ext[idx], 0)], -1)
    out = Tree(t.start[idx], t.axis[idx], t.length[idx], t.radius[idx],
               par, ext, t.name, t.species, dict(t.meta))
    return out.recompute_topology()


def save_npz(t, path):
    np.savez_compressed(path, start=t.start.astype(np.float32),
                        axis=t.axis.astype(np.float32),
                        length=t.length.astype(np.float32),
                        radius=t.radius.astype(np.float32),
                        parent=t.parent.astype(np.int32), ext=t.ext.astype(np.int32),
                        name=t.name, species=t.species)


def load_npz(path):
    z = np.load(path)
    return Tree(z['start'].astype(float), z['axis'].astype(float),
                z['length'].astype(float), z['radius'].astype(float),
                z['parent'].astype(np.int64), z['ext'].astype(np.int64),
                str(z['name']), str(z['species'])).recompute_topology()


# ---------------------------------------------------------------- marcos locales

def _minrot(a, b):
    """Rotación mínima que lleva el vector unitario a sobre b."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -1 + 1e-9:
        p =np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
        p -= a * np.dot(a, p)
        p /= np.linalg.norm(p)
        return 2 * np.outer(p, p) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + (vx @ vx) / (1 + c)


def _ortho(F):
    """Re-ortonormaliza un marco conservando su tercera columna (el eje)."""
    w = F[:, 2] / np.linalg.norm(F[:, 2])
    u = F[:, 0] - w * np.dot(w, F[:, 0])
    u /= np.linalg.norm(u)
    return np.column_stack([u, np.cross(w, u), w])


def _root_frame(w):
    ref = np.array([1.0, 0, 0]) if abs(w[0]) < 0.9 else np.array([0, 1.0, 0])
    u = ref - w * np.dot(w, ref)
    u /= np.linalg.norm(u)
    return np.column_stack([u, np.cross(w, u), w])


@dataclass
class Local:
    """Árbol codificado en marcos locales (todo relativo al padre)."""
    root_start: np.ndarray
    root_frame: np.ndarray
    tuv: np.ndarray      # (n,3): t a lo largo del padre (fracción de longitud), u, v radiales (fracción del radio)
    aloc: np.ndarray     # (n,3): eje en el marco del padre
    length: np.ndarray
    radius: np.ndarray
    parent: np.ndarray
    ext: np.ndarray


def encode(t):
    n = t.n
    frames = np.zeros((n, 3, 3))
    tuv = np.zeros((n, 3))
    aloc = np.zeros((n, 3))
    frames[0] = _root_frame(t.axis[0])
    aloc[0] = (0, 0, 1)
    for i in range(1, n):
        p = t.parent[i]
        F = frames[p]
        d = F.T @ (t.start[i] - t.start[p])
        tuv[i] = (d[2] / max(t.length[p], 1e-9), d[0] / max(t.radius[p], 1e-9),
                  d[1] / max(t.radius[p], 1e-9))
        aloc[i] = F.T @ t.axis[i]
        frames[i] = _ortho(_minrot(F[:, 2], t.axis[i]) @ F)
    return Local(t.start[0].copy(), frames[0], tuv, aloc, t.length.copy(),
                 t.radius.copy(), t.parent.copy(), t.ext.copy())


def decode(L, name='', species=''):
    n = len(L.length)
    start = np.zeros((n, 3))
    axis = np.zeros((n, 3))
    frames = np.zeros((n, 3, 3))
    start[0] = L.root_start
    frames[0] = L.root_frame
    axis[0] = L.root_frame[:, 2]
    for i in range(1, n):
        p = L.parent[i]
        F = frames[p]
        tt, uu, vv = L.tuv[i]
        start[i] = start[p] + F @ np.array([uu * L.radius[p], vv * L.radius[p], tt * L.length[p]])
        a = F @ L.aloc[i]
        a /= np.linalg.norm(a)
        axis[i] = a
        frames[i] = _ortho(_minrot(F[:, 2], a) @ F)
    return Tree(start, axis, L.length.copy(), L.radius.copy(), L.parent.copy(),
                L.ext.copy(), name, species).recompute_topology()

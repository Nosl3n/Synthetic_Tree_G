#!/usr/bin/env python3
"""Vary TreeQSM models at the cylinder-table level.

Each input is a TreeQSM .mat file containing a single `QSM` struct whose
`cylinder` table holds the geometric model (start point, unit axis, radius,
length, and the parent/extension/branch topology).  This script perturbs the
cylinder table directly -- radius (primary), and optionally length or axis
orientation -- then recomputes the metrics that follow from the cylinder table,
and saves a new QSM.

Conventions (matching TreeQSM output):
  * radii / lengths / coordinates are in metres
  * volume fields  (treedata.TotalVolume, branch.volume, ...) in litres (m^3 * 1000)
  * area fields    (treedata.TotalArea,   branch.area,   ...) in m^2
  * length fields  (treedata.TotalLength, branch.length, ...) in metres
  * branch.diameter = 2 * radius of the branch's base (first) cylinder

The cylinder topology (parent / extension / branch / order indices) is left
untouched, so every new QSM keeps the exact branching structure of its source.
The complex distribution fields in `treedata` (StemTaper, VerticalProfile,
VolCylDia histograms, ...) are NOT recomputed and remain those of the source
model; only the aggregate volume/area/length metrics are refreshed.
"""

import argparse
import csv
import os
import sys
from collections import deque

import numpy as np
import scipy.io as sio


# --------------------------------------------------------------------------- #
# Loading / saving
# --------------------------------------------------------------------------- #
def load_qsm(path):
    """Load a TreeQSM .mat file and return the `QSM` mat_struct."""
    d = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    key = 'QSM' if 'QSM' in d else next((k for k in d if not k.startswith('__')), None)
    if key is None:
        raise ValueError(f'No QSM data in {path}: {sorted(d.keys())}')
    return d[key]


def _mat_to_dict(obj):
    """Recursively convert a mat_struct into a nested dict for savemat."""
    if hasattr(obj, '_fieldnames'):  # scipy mat_struct (duck-typed)
        return {fn: _mat_to_dict(getattr(obj, fn)) for fn in obj._fieldnames}
    if isinstance(obj, np.ndarray) and obj.dtype == object:
        out = np.empty(obj.shape, dtype=object)
        for idx in np.ndindex(obj.shape):
            out[idx] = _mat_to_dict(obj[idx])
        return out
    return obj


def save_qsm(q, path):
    """Save the QSM struct back to a MATLAB v5 .mat file (column-major, as source)."""
    sio.savemat(path, {'QSM': _mat_to_dict(q)}, do_compression=False)


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _cyl_volume_m3(radius, length):
    return np.pi * radius.astype(np.float64) ** 2 * length.astype(np.float64)


def _cyl_area_m2(radius, length):
    return 2.0 * np.pi * radius.astype(np.float64) * length.astype(np.float64)


def topological_order(parent, n):
    """Cylinder indices in parent-before-child order (parent is 1-based, 0 = root)."""
    children = [[] for _ in range(n)]
    for i in range(n):
        p = int(parent[i])
        if p > 0:
            children[p - 1].append(i)
    order = []
    visited = [False] * n
    for i in range(n):
        if int(parent[i]) == 0 and not visited[i]:
            dq = deque([i])
            visited[i] = True
            while dq:
                x = dq.popleft()
                order.append(x)
                for c in children[x]:
                    if not visited[c]:
                        visited[c] = True
                        dq.append(c)
    for i in range(n):
        if not visited[i]:
            order.append(i)
    return order


def recompute_metrics(q):
    """Refresh branch-level and tree-level metrics from the cylinder table."""
    cy = q.cylinder
    r = cy.radius.astype(np.float64)
    L = cy.length.astype(np.float64)
    vol_m3 = _cyl_volume_m3(r, L)
    area_m2 = _cyl_area_m2(r, L)

    n_cyl = len(r)
    branch_ids = cy.branch.astype(np.int64)          # 1-based branch id
    n_branch = int(branch_ids.max()) if n_cyl else 0

    br = q.branch
    bvol = np.zeros(n_branch, dtype=np.float64)
    barea = np.zeros(n_branch, dtype=np.float64)
    blen = np.zeros(n_branch, dtype=np.float64)
    bdiam = np.zeros(n_branch, dtype=np.float64)
    for b in range(1, n_branch + 1):
        m = branch_ids == b
        bvol[b - 1] = vol_m3[m].sum()
        barea[b - 1] = area_m2[m].sum()
        blen[b - 1] = L[m].sum()
        pos = cy.PositionInBranch[m].astype(np.int64)
        base = np.where(m)[0][int(np.argmin(pos))]
        bdiam[b - 1] = 2.0 * r[base]

    br.volume[:] = (bvol * 1000.0).astype(np.float32)      # litres
    br.area[:] = barea.astype(np.float32)                  # m^2
    br.length[:] = blen.astype(np.float32)                 # m
    br.diameter[:] = bdiam.astype(np.float32)              # m

    td = q.treedata
    trunk = cy.BranchOrder.astype(np.int64) == 0
    td.TotalVolume = float(vol_m3.sum() * 1000.0)
    td.TotalArea = float(area_m2.sum())
    td.TotalLength = float(L.sum())
    td.TrunkVolume = float(vol_m3[trunk].sum() * 1000.0)
    td.BranchVolume = float(vol_m3[~trunk].sum() * 1000.0)
    td.TrunkArea = float(area_m2[trunk].sum())
    td.BranchArea = float(area_m2[~trunk].sum())
    td.TrunkLength = float(L[trunk].sum())
    td.BranchLength = float(L[~trunk].sum())

    _recompute_dbh(q)


def _recompute_dbh(q):
    """Best-effort DBHcyl (m) = diameter of the trunk cylinder spanning 1.3 m."""
    try:
        cy = q.cylinder
        trunk = cy.BranchOrder.astype(np.int64) == 0
        idx = np.where(trunk)[0]
        if len(idx) == 0:
            return
        z = cy.start[:, 2].astype(np.float64)
        axis_z = cy.axis[:, 2].astype(np.float64)
        L = cy.length.astype(np.float64)
        r = cy.radius.astype(np.float64)
        base_z = float(z[idx].min())
        bh = base_z + 1.3
        best = None
        for i in idx:
            z0 = float(z[i])
            z1 = z0 + float(L[i]) * float(axis_z[i])
            lo, hi = min(z0, z1), max(z0, z1)
            if lo <= bh <= hi:
                q.treedata.DBHcyl = float(2.0 * r[i])
                return
            d = min(abs(z0 - bh), abs(z1 - bh))
            if best is None or d < best[0]:
                best = (d, i)
        if best is not None:
            q.treedata.DBHcyl = float(2.0 * r[best[1]])
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Perturbations
# --------------------------------------------------------------------------- #
def perturb_radii(q, frac=0.10, seed=0):
    """Multiply every cylinder radius by an iid U(1-frac, 1+frac) factor."""
    rng = np.random.default_rng(seed)
    cy = q.cylinder
    factor = rng.uniform(1.0 - frac, 1.0 + frac, size=len(cy.radius))
    cy.radius[:] = (cy.radius.astype(np.float64) * factor).astype(np.float32)
    recompute_metrics(q)
    return factor


def perturb_lengths(q, frac=0.05, seed=0):
    """Scale cylinder lengths and re-link child start points (topology preserved)."""
    rng = np.random.default_rng(seed)
    cy = q.cylinder
    n = len(cy.length)
    factor = rng.uniform(1.0 - frac, 1.0 + frac, size=n)
    new_len = (cy.length.astype(np.float64) * factor).astype(np.float32)
    axis = cy.axis.astype(np.float32)
    new_start = cy.start.astype(np.float32).copy()
    new_end = np.empty_like(new_start)
    order = topological_order(cy.parent, n)
    for i in order:
        p = int(cy.parent[i])
        if p > 0:
            new_start[i] = new_end[p - 1]
        new_end[i] = new_start[i] + new_len[i] * axis[i]
    cy.length[:] = new_len
    cy.start[:] = new_start
    recompute_metrics(q)
    return factor


def _rotate_vector(v, k, theta):
    """Rodrigues rotation of v about unit axis k by angle theta."""
    return (v * np.cos(theta)
            + np.cross(k, v) * np.sin(theta)
            + k * np.dot(k, v) * (1.0 - np.cos(theta)))


def perturb_axes(q, angle_deg=3.0, seed=0):
    """Rotate each cylinder axis by a small random angle, re-link start points."""
    rng = np.random.default_rng(seed)
    cy = q.cylinder
    n = len(cy.axis)
    new_axis = cy.axis.astype(np.float64).copy()
    for i in range(n):
        a = new_axis[i]
        a = a / (np.linalg.norm(a) + 1e-12)
        theta = rng.uniform(0.0, np.radians(angle_deg))
        v = rng.standard_normal(3)
        v = v - np.dot(v, a) * a
        nv = np.linalg.norm(v)
        if nv < 1e-9:
            v = np.cross(a, [1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.cross(a, [0.0, 1.0, 0.0])
            v = v - np.dot(v, a) * a
            nv = np.linalg.norm(v)
        v = v / nv
        new_axis[i] = _rotate_vector(a, v, theta)
        new_axis[i] /= np.linalg.norm(new_axis[i])
    new_axis = new_axis.astype(np.float32)
    length = cy.length.astype(np.float32)
    new_start = cy.start.astype(np.float32).copy()
    new_end = np.empty_like(new_start)
    order = topological_order(cy.parent, n)
    for i in order:
        p = int(cy.parent[i])
        if p > 0:
            new_start[i] = new_end[p - 1]
        new_end[i] = new_start[i] + length[i] * new_axis[i]
    cy.axis[:] = new_axis
    cy.start[:] = new_start
    recompute_metrics(q)
    return new_axis


PERTURB = {'radius': perturb_radii, 'length': perturb_lengths, 'axis': perturb_axes}


# --------------------------------------------------------------------------- #
# Reporting helpers
# --------------------------------------------------------------------------- #
def qsm_metrics(q):
    """Aggregate metrics (TreeQSM units) computed straight from the cylinder table."""
    cy = q.cylinder
    r = cy.radius.astype(np.float64)
    L = cy.length.astype(np.float64)
    vol = _cyl_volume_m3(r, L) * 1000.0
    return {
        'n_cylinders': int(len(r)),
        'total_volume_L': float(vol.sum()),
        'total_area_m2': float(_cyl_area_m2(r, L).sum()),
        'total_length_m': float(L.sum()),
    }


def qsm_source_info(q):
    """Return (tree_name, model_index) from rundata.inputs if available."""
    try:
        return str(q.rundata.inputs.name), int(q.rundata.inputs.model)
    except Exception:
        return '', 0


CYL_COLUMNS = [
    'qsm_id', 'variant', 'seed', 'mode', 'frac',
    'cyl_id', 'radius', 'length',
    'start_x', 'start_y', 'start_z',
    'axis_x', 'axis_y', 'axis_z',
    'parent', 'extension', 'branch', 'branch_order', 'position_in_branch',
    'volume_L',
]

SUMMARY_COLUMNS = [
    'qsm_id', 'tree', 'model', 'variant', 'seed', 'mode', 'frac',
    'n_cylinders',
    'vol_before_L', 'vol_after_L', 'vol_pct_change',
    'area_before_m2', 'area_after_m2',
    'length_before_m', 'length_after_m',
]


def iter_cylinder_rows(q, qsm_id, variant, seed, mode, frac):
    cy = q.cylinder
    vol = _cyl_volume_m3(cy.radius, cy.length) * 1000.0
    for i in range(len(cy.radius)):
        s = cy.start[i]
        a = cy.axis[i]
        yield [
            qsm_id, variant, seed, mode, frac, i,
            float(cy.radius[i]), float(cy.length[i]),
            float(s[0]), float(s[1]), float(s[2]),
            float(a[0]), float(a[1]), float(a[2]),
            int(cy.parent[i]), int(cy.extension[i]), int(cy.branch[i]),
            int(cy.BranchOrder[i]), int(cy.PositionInBranch[i]),
            float(vol[i]),
        ]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description='Vary TreeQSM models at the cylinder-table level.')
    ap.add_argument('--input', required=True, help='Directory of .mat QSM files.')
    ap.add_argument('--output', required=True, help='Output directory.')
    ap.add_argument('--mode', choices=sorted(PERTURB), default='radius')
    ap.add_argument('--frac', type=float, default=0.10,
                    help='Radius/length perturbation fraction (default 0.10 = +/-10%%).')
    ap.add_argument('--axis-deg', type=float, default=3.0,
                    help='Max axis rotation angle in degrees (mode=axis).')
    ap.add_argument('--seeds', type=int, nargs='+', default=[0, 1, 2],
                    help='Random seeds, one variant each (default 0 1 2).')
    ap.add_argument('--limit', type=int, default=0,
                    help='Process at most this many files (0 = all).')
    ap.add_argument('--no-mat', action='store_true',
                    help='Skip writing new .mat files (cylinder CSV only).')
    args = ap.parse_args(argv)

    files = sorted(
        f for f in os.listdir(args.input)
        if f.lower().endswith('.mat') and not f.startswith('._')
    )
    if args.limit:
        files = files[: args.limit]
    if not files:
        print('No .mat files found in', args.input)
        return 1

    mat_dir = os.path.join(args.output, 'mat')
    csv_dir = os.path.join(args.output, 'cylinders')
    os.makedirs(mat_dir, exist_ok=True)
    os.makedirs(csv_dir, exist_ok=True)

    summary_path = os.path.join(args.output, 'summary.csv')
    mode = args.mode
    frac = args.frac
    frac_label = args.axis_deg if mode == 'axis' else frac

    with open(summary_path, 'w', newline='') as sf:
        sw = csv.writer(sf)
        sw.writerow(SUMMARY_COLUMNS)
        n_done = 0
        for name in files:
            stem = os.path.splitext(name)[0]
            src = os.path.join(args.input, name)
            try:
                tree_name, model_idx = qsm_source_info(load_qsm(src))
            except Exception as e:
                print(f'[skip] {name}: {e}', file=sys.stderr)
                continue

            for seed in args.seeds:
                try:
                    qv = load_qsm(src)  # fresh copy per variant
                except Exception as e:
                    print(f'[skip] {name}: {e}', file=sys.stderr)
                    break
                before_v = qsm_metrics(qv)
                if mode == 'axis':
                    PERTURB[mode](qv, angle_deg=args.axis_deg, seed=seed)
                else:
                    PERTURB[mode](qv, frac=frac, seed=seed)
                after_v = qsm_metrics(qv)

                label = f'{mode}{frac_label:.2f}'.replace('.', 'p')
                variant = f'{label}_s{seed}'
                pct = 100.0 * (after_v['total_volume_L'] - before_v['total_volume_L']) / before_v['total_volume_L']
                sw.writerow([
                    stem, tree_name, model_idx, variant, seed, mode, frac_label,
                    before_v['n_cylinders'],
                    round(before_v['total_volume_L'], 3),
                    round(after_v['total_volume_L'], 3),
                    round(pct, 4),
                    round(before_v['total_area_m2'], 3),
                    round(after_v['total_area_m2'], 3),
                    round(before_v['total_length_m'], 3),
                    round(after_v['total_length_m'], 3),
                ])

                if not args.no_mat:
                    out_mat = os.path.join(mat_dir, f'{stem}__{variant}.mat')
                    save_qsm(qv, out_mat)

                out_csv = os.path.join(csv_dir, f'{stem}__{variant}.csv')
                with open(out_csv, 'w', newline='') as cf:
                    cw = csv.writer(cf)
                    cw.writerow(CYL_COLUMNS)
                    cw.writerows(iter_cylinder_rows(qv, stem, variant, seed, mode, frac_label))

            n_done += 1
            if n_done % 100 == 0:
                print(f'... {n_done}/{len(files)}', flush=True)

    print(f'Done: {n_done} files -> {args.output}')
    print(f'  summary:  {summary_path}')
    print(f'  cylinders: {csv_dir}')
    if not args.no_mat:
        print(f'  mat:      {mat_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

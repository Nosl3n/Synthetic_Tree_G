#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Angel Marquez Aguilar
"""Extract full trunk taper profiles (radius vs relative height) for every QSM.

For each TreeQSM ``.mat`` the trunk is the set of cylinders with ``branch == 0``.
This script records, for every trunk cylinder, its relative height (mid-point
height / trunk height) and its radius normalised by the radius at 1.3 m (r13),
then writes one profile row per cylinder and a per-species summary at the same
nine relative heights the paper uses (0.1 .. 0.9).

Outputs:
  taper/taper_profiles.csv   tree, species, rel_height, radius_norm
  taper/taper_summary.csv    species, n_trees, taper_01 .. taper_09
"""
import os
import sys
import csv
import glob

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'synth_trees'))
import qsm  # noqa: E402

TAPER_H = np.round(np.arange(0.1, 1.0, 0.1), 1)


def trunk_taper(t):
    """Return (rel_height, radius_norm) arrays for the trunk cylinders."""
    tr = np.where(t.branch == 0)[0]
    if len(tr) == 0:
        return None
    z0 = t.start[0, 2]
    zs = t.start[tr, 2] - z0
    ze = t.end[tr, 2] - z0
    zmid = (zs + ze) / 2.0
    trunk_h = float(ze.max())
    if trunk_h <= 0:
        return None

    def r_at(z):
        k = np.where((zs <= z) & (ze >= z))[0]
        if len(k):
            return float(t.radius[tr[k[0]]])
        return float(t.radius[tr[int(np.argmin(np.abs(zmid - z)))]])

    r13 = r_at(1.3)
    if r13 <= 0:
        return None
    order = np.argsort(zmid)
    return zmid[order] / trunk_h, t.radius[tr][order].astype(float) / r13


def main():
    mats = sorted(glob.glob(f'{HERE}/mat/MultipleQSMModels/*.mat'))
    prof_path = f'{HERE}/taper/taper_profiles.csv'
    summ_path = f'{HERE}/taper/taper_summary.csv'
    os.makedirs(f'{HERE}/taper', exist_ok=True)

    species_rows = {}  # species -> list of (rel, rn) arrays
    with open(prof_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['tree', 'species', 'rel_height', 'radius_norm'])
        n = 0
        for p in mats:
            t = qsm.load_mat(p)
            pr = trunk_taper(t)
            if pr is None:
                continue
            rel, rn = pr
            for h, r in zip(rel, rn):
                w.writerow([t.name, t.species, round(float(h), 4), round(float(r), 4)])
            species_rows.setdefault(t.species, []).append((rel, rn))
            n += 1
            if n % 500 == 0:
                print(f'... {n}/{len(mats)}', flush=True)
    print('wrote', prof_path, f'({n} files)')

    with open(summ_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['species', 'n_trees', *[f'taper_{int(h * 10):02d}' for h in TAPER_H]])
        for sp in sorted(species_rows):
            rows = species_rows[sp]
            means = []
            for h in TAPER_H:
                vals = [float(np.interp(h, rel, rn)) for rel, rn in rows]
                means.append(round(float(np.mean(vals)), 4))
            w.writerow([sp, len(rows), *means])
    print('wrote', summ_path)


if __name__ == '__main__':
    main()

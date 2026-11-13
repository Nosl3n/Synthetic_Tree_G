#!/usr/bin/env python3
"""Consolidate QSM cylinder tables into a single portable Parquet file.

Reads original and/or varied TreeQSM .mat files and writes one Parquet table
with one row per cylinder.  Units: radius/length/coords in metres, volume in
litres (m^3 * 1000).
"""
import argparse
import os

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import scipy.io as sio

COLUMNS = [
    'qsm_id', 'tree', 'model', 'variant', 'seed', 'cyl_id',
    'radius', 'length', 'volume_L',
    'start_x', 'start_y', 'start_z',
    'axis_x', 'axis_y', 'axis_z',
    'parent', 'extension', 'branch', 'branch_order', 'position_in_branch',
]


def load_qsm(path):
    d = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    key = 'QSM' if 'QSM' in d else next(k for k in d if not k.startswith('__'))
    return d[key]


def source_info(q):
    try:
        return str(q.rundata.inputs.name), int(q.rundata.inputs.model)
    except Exception:
        return '', 0


def build_df(q, qsm_id, tree, model, variant, seed):
    cy = q.cylinder
    n = len(cy.radius)
    r = cy.radius.astype(np.float64)
    L = cy.length.astype(np.float64)
    vol = np.pi * r * r * L * 1000.0
    st = cy.start.astype(np.float64)
    ax = cy.axis.astype(np.float64)
    return pd.DataFrame({
        'qsm_id': [qsm_id] * n,
        'tree': [tree] * n,
        'model': np.full(n, model, dtype=np.int16),
        'variant': [variant] * n,
        'seed': np.full(n, seed, dtype=np.int8),
        'cyl_id': np.arange(n, dtype=np.int32),
        'radius': cy.radius.astype(np.float32),
        'length': cy.length.astype(np.float32),
        'volume_L': vol.astype(np.float32),
        'start_x': st[:, 0].astype(np.float32),
        'start_y': st[:, 1].astype(np.float32),
        'start_z': st[:, 2].astype(np.float32),
        'axis_x': ax[:, 0].astype(np.float32),
        'axis_y': ax[:, 1].astype(np.float32),
        'axis_z': ax[:, 2].astype(np.float32),
        'parent': cy.parent.astype(np.int32),
        'extension': cy.extension.astype(np.int32),
        'branch': cy.branch.astype(np.int32),
        'branch_order': cy.BranchOrder.astype(np.int16),
        'position_in_branch': cy.PositionInBranch.astype(np.int16),
    })


def parse_variant(stem):
    """Split a varied filename stem into (base_stem, variant, seed)."""
    if '__' in stem:
        base, v = stem.rsplit('__', 1)
        try:
            seed = int(v.rsplit('_s', 1)[1])
        except Exception:
            seed = 0
        return base, v, seed
    return stem, 'original', -1


def iter_files(dirs):
    for d in dirs:
        for f in sorted(os.listdir(d)):
            if f.lower().endswith('.mat') and not f.startswith('._'):
                yield os.path.join(d, f), f[:-4]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dirs', nargs='+', required=True,
                    help='One or more dirs of .mat files (originals and/or varied).')
    ap.add_argument('--out', required=True, help='Output .parquet path.')
    args = ap.parse_args()

    schema = pa.schema([
        ('qsm_id', pa.string()), ('tree', pa.string()), ('model', pa.int16()),
        ('variant', pa.string()), ('seed', pa.int8()), ('cyl_id', pa.int32()),
        ('radius', pa.float32()), ('length', pa.float32()), ('volume_L', pa.float32()),
        ('start_x', pa.float32()), ('start_y', pa.float32()), ('start_z', pa.float32()),
        ('axis_x', pa.float32()), ('axis_y', pa.float32()), ('axis_z', pa.float32()),
        ('parent', pa.int32()), ('extension', pa.int32()), ('branch', pa.int32()),
        ('branch_order', pa.int16()), ('position_in_branch', pa.int16()),
    ])
    writer = pq.ParquetWriter(args.out, schema, compression='zstd')

    n_files = 0
    for path, stem in iter_files(args.dirs):
        try:
            q = load_qsm(path)
            tree, model = source_info(q)
        except Exception as e:
            print(f'[skip] {path}: {e}', flush=True)
            continue
        base, variant, seed = parse_variant(stem)
        df = build_df(q, base, tree, model, variant, seed)
        writer.write_table(pa.Table.from_pandas(df, schema=schema, preserve_index=False))
        n_files += 1
        if n_files % 500 == 0:
            print(f'... {n_files} files', flush=True)

    writer.close()
    print(f'Wrote {n_files} QSMs to {args.out}')
    print(f'  columns: {", ".join(COLUMNS)}')


if __name__ == '__main__':
    main()

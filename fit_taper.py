#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Angel Marquez Aguilar
"""Bayesian hierarchical trunk-taper fit (Direction 2, first step).

Model for a species' trunk cylinders (log radius vs. relative height x in [0,1]):

    log(r_i) = alpha + u_{tree_i} + beta * x_i + eps_i
    u_t ~ N(0, sigma_u^2),   eps_i ~ N(0, sigma_e^2)

Fully conjugate -> exact Gibbs sampler (no MCMC tuning). The posterior over
(alpha, beta, sigma_u, sigma_e) lets us SAMPLE new taper curves: a new tree is
a draw of u ~ N(0, sigma_u^2) applied to the shared species taper shape.
"""
import os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
PARQUET = os.path.join(HERE, 'qsms.parquet')
OUT = os.path.join(HERE, 'taper')
SPECIES = 'ALBLAC'


def extract_trunk_taper(parquet, species):
    """Relative-height x and log-radius y for trunk cylinders of one species."""
    t = pq.read_table(
        parquet,
        columns=['tree', 'variant', 'branch_order', 'radius', 'start_z', 'length', 'axis_z'],
        filters=[('variant', '==', 'original'), ('branch_order', '==', 0)],
    )
    df = t.to_pandas()
    df['species'] = df['tree'].str.split('_').str[0]
    df = df[df['species'] == species].copy()
    df['end_z'] = df['start_z'] + df['length'] * df['axis_z']
    g = df.groupby('tree')
    base = g['start_z'].transform('min')
    top = g['end_z'].transform('max')
    span = (top - base).replace(0, np.nan)
    df['x'] = (df['start_z'] - base) / span
    df = df[df['x'].between(0.0, 1.0)]
    df['y'] = np.log(df['radius'].astype(float))
    return df[['tree', 'x', 'y', 'radius']]


def gibbs(x, y, tree_idx, n_trees, iters=4000, burn=1000, seed=0):
    """Exact Gibbs sampler for the hierarchical linear model above.

    Uses hierarchical centering: mu_t = alpha + u_t (per-tree intercept) so the
    intercept and the random effects don't trade off (which otherwise makes a
    naive parameterization mix extremely slowly).
    """
    rng = np.random.default_rng(seed)
    n = len(y)
    a, b = 1e-3, 1e-3          # InvGamma for variances
    tau2 = 100.0               # prior var for alpha, beta (diffuse)

    mu = np.zeros(n_trees)     # mu_t = alpha + u_t
    alpha = float(np.mean(y))
    beta = -1.0
    se2 = 0.1
    su2 = 0.1

    chain = {'alpha': [], 'beta': [], 'sigma_u': [], 'sigma_e': []}
    xx = x.astype(float)
    sum_x2 = float(np.sum(xx * xx))

    for it in range(iters + burn):
        # 1) mu_t | rest  (prior mu_t ~ N(alpha, su2))
        resid = y - beta * xx
        for t in range(n_trees):
            m = tree_idx == t
            nt = m.sum()
            s = resid[m].sum()
            prec = nt / se2 + 1.0 / su2
            mu[t] = rng.normal((s / se2 + alpha / su2) / prec, np.sqrt(1.0 / prec))

        # 2) alpha | rest  -> N(mean(mu_t), su2 / n_trees)
        alpha = rng.normal(mu.mean(), np.sqrt(su2 / n_trees))

        # 3) beta | rest  (no-intercept regression of y - mu on x)
        yc = y - mu[tree_idx]
        prec_b = sum_x2 / se2 + 1.0 / tau2
        mean_b = (np.sum(xx * yc) / se2) / prec_b
        beta = rng.normal(mean_b, np.sqrt(1.0 / prec_b))

        # 4) sigma_e^2 | rest  (InvGamma)
        ssr = np.sum((yc - beta * xx) ** 2)
        se2 = 1.0 / rng.gamma(a + n / 2.0, 1.0 / (b + ssr / 2.0))

        # 5) sigma_u^2 | rest  (InvGamma, from mu - alpha)
        su2 = 1.0 / rng.gamma(a + n_trees / 2.0, 1.0 / (b + np.sum((mu - alpha) ** 2) / 2.0))

        if it >= burn:
            chain['alpha'].append(alpha)
            chain['beta'].append(beta)
            chain['sigma_u'].append(np.sqrt(su2))
            chain['sigma_e'].append(np.sqrt(se2))

    return {k: np.asarray(v) for k, v in chain.items()}


def main():
    os.makedirs(OUT, exist_ok=True)
    df = extract_trunk_taper(PARQUET, SPECIES)
    df.to_csv(f'{OUT}/taper_{SPECIES}.csv', index=False)

    trees = df['tree'].astype('category')
    tree_idx = trees.cat.codes.to_numpy()
    n_trees = len(trees.cat.categories)
    x = df['x'].to_numpy(float)
    y = df['y'].to_numpy(float)
    print(f'{SPECIES}: {len(df)} trunk cylinders, {n_trees} trees')

    chain = gibbs(x, y, tree_idx, n_trees)
    for k, v in chain.items():
        print(f'  {k}: mean={v.mean():.3f}  sd={v.std():.3f}  '
              f'[95% {np.percentile(v,2.5):.3f}, {np.percentile(v,97.5):.3f}]')

    # --- posterior-sampled taper curves vs original data ---
    a_ = chain['alpha']; b_ = chain['beta']
    xg = np.linspace(0.0, 1.0, 100)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))

    ax[0].scatter(df['x'], df['radius'], s=2, alpha=0.05, color='0.3', label='original ALBLAC trunk')
    # posterior mean curve
    r_mean = np.exp(a_.mean() + b_.mean() * xg)
    ax[0].plot(xg, r_mean, color='tab:red', lw=2, label='posterior mean taper')
    # 20 sampled curves (new random tree each)
    for k in range(20):
        idx = np.random.default_rng(k).integers(0, len(a_))
        u_new = np.random.default_rng(k + 1000).normal(0, np.median(chain['sigma_u']))
        ax[0].plot(xg, np.exp(a_[idx] + u_new + b_[idx] * xg),
                   color='tab:blue', lw=0.6, alpha=0.4)
    ax[0].set_xlabel('relative height along trunk x')
    ax[0].set_ylabel('radius (m)')
    ax[0].set_title(f'{SPECIES} trunk taper — original vs posterior samples')
    ax[0].legend(fontsize=8)

    # --- one tree: original radii vs a synthetic (resampled) version ---
    one = df[df['tree'] == trees.cat.categories[0]].sort_values('x')
    r_synth = np.exp(a_.mean() + np.random.default_rng(7).normal(0, np.median(chain['sigma_u'])) + b_.mean() * one['x'].to_numpy())
    ax[1].scatter(one['x'], one['radius'], s=10, color='0.2', label='original (one tree)')
    ax[1].scatter(one['x'], r_synth, s=10, color='tab:green', label='synthetic (posterior sample)')
    ax[1].set_xlabel('relative height x')
    ax[1].set_ylabel('radius (m)')
    ax[1].set_title('Same tree: original vs synthetic radii')
    ax[1].legend(fontsize=8)

    fig.tight_layout()
    png = f'{OUT}/taper_{SPECIES}.png'
    fig.savefig(png, dpi=150)
    print('wrote', png)


if __name__ == '__main__':
    main()

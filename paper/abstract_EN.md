# Synthetic_Tree_G — abstract (English)

Machine-learning models that work with 3D tree data need large numbers of labelled
examples, which are expensive to obtain. This work studies how to generate realistic
synthetic trees from real quantitative structure models (QSMs) — cylinder models
reconstructed from scanned trees — and how to measure whether the synthetic trees
resemble the real ones.

We use 201 QSMs of tropical trees scanned with terrestrial laser scanning on Barro
Colorado Island (Panama) as a representative, publicly available test bed (feasible to
download and work with). We implement eight generators covering the three families in
the literature: (i) methods that learn from real trees (perturbation, allometric
perturbation, same-species branch recombination, a hybrid, and a procedural generator
that samples rules from real branches); (ii) a generator based only on botanical rules
(allometry, phyllotaxis, taper profiles); and (iii) a classical growth algorithm (space
colonization).

We evaluate them against unseen real trees using normalized Wasserstein distances over
22 tree traits and 10 branch traits, a nearest-neighbour two-sample test (1-NNA), a
novelty metric, and botanical-validity rules. Same-species branch recombination (G2) is
the most faithful (1-NNA = 56 % vs 46 % among real trees); the procedural generator (G4)
is the most novel among realistic ones; their mix G2+G4 keeps the fidelity of G2 while
nearly doubling novelty (0.73 → 1.19).

The core goal is **synthetic data generation — more, diverse examples for downstream
models** — not any single application. The same cylinder representation and generators
transfer directly to agricultural and orchard trees (e.g. apple): a low trunk and a
spreading, often pruned crown are the same cylinder-table machinery. As one downstream
use, we build a virtual forest of 24 synthetic trees in NVIDIA Isaac Sim, with simulated
LiDAR and RGB-D producing automatically-labelled data in real time — but this is a means
to generate labelled examples, not the purpose.

*Full paper (Spanish): `paper/main.pdf`.*

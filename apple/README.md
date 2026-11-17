# `apple/`: apple-tree QSMs for the orchard transfer

| File | What it is | Licence |
|---|---|---|
| `bibaum_prepruned.npz` | Real apple tree "Bibaum A" before winter pruning, 2020: 131 cylinders | CC BY 4.0, see below |
| `bibaum_pruned.npz` | The same tree after the 2020 winter pruning (scanned 30 March 2020): 99 cylinders | CC BY 4.0, see below |
| `apple_real_vs_tropical.png`, `apple_vs_tropical_deck.png` | Figures showing the Bibaum tree beside procedural and tropical QSMs | CC BY 4.0, see below |
| `apple_procedural.npz`, `apple_vs_tropical.png` | Procedural open-centre apple tree (`make_apple_comparison.py`) and its comparison figure | MIT (repository `LICENSE`) |

Each `.npz` holds one `Tree` in the format of `synth_trees/qsm.py`: `start`, `axis`, `length`, `radius` (metres),
`parent`, `ext`, `name`, `species`.

## Where the Bibaum data come from

- **Tree:** one apple tree, "Bibaum A", in the experimental orchard of Wageningen University & Research at
  Randwijk, the Netherlands.
- **Measurement:** terrestrial laser scans (RIEGL VZ-400) of the same tree before and after the 2020 winter pruning;
  the pruning was done between 11 and 30 March 2020, and the after-pruning scan is from 30 March.
- **Model:** a TreeQSM 2.4.0 model of the pre-pruning scan (66 branches, 659 cylinders) by Angel Marquez Aguilar.
  The fate of each branch (removed, shortened, kept) comes from comparing the before and after scans.
- **These files:** a coarse, connected skeleton of that model (one polyline per branch through its children's
  insertion points), exported as a GroIMP `.qsm` table on 27 October 2026 and converted to this repository's format by
  `borrow_apple_qsm.py`; later exports of the pruned tree differ (97 cylinders since 7 November 2026). They are simplified examples: neither the full 659-cylinder model nor the point clouds.

## Licence and how to credit

The Bibaum files and figures listed above, the slides of the English deck (`paper/`) that show the Bibaum tree
or its scans, and the pruning video `paper/videos/pruning_agent.mp4` (credit line in `paper/README.md`) are © 2026 Angel Marquez Aguilar, licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
You may share and adapt them for any purpose, provided you:

1. credit the source, for example:
   > Bibaum A apple-tree QSM examples (WUR Randwijk, terrestrial laser scans 2020) by Angel Marquez Aguilar,
   > from Synthetic_Tree_G (https://github.com/Nosl3n/Synthetic_Tree_G), licensed CC BY 4.0;
2. link to the licence; and
3. say whether you changed the data (for example: resampled, varied, converted).

In a paper, cite the repository as `CITATION.cff` describes; its `references` list includes these examples.

The code that produced them (`borrow_apple_qsm.py` and the other scripts by Angel Marquez Aguilar in this
repository) is under the repository's MIT licence.

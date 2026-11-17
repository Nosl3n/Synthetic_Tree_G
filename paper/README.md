# `paper/`: paper, presentation and videos

The Spanish paper (`main.tex`, `refs.bib`, `figs/`, `main.pdf`) and the English presentation of the
Sino-European Masterclass 2026, with its two videos.

## Presentation

| File | What it is |
|---|---|
| `Synthetic_Tree_G_masterclass_slides_EN.pdf` | The English presentation as shown at the masterclass (16 slides) |
| `Synthetic_Tree_G_presentation_EN.pptx` | Editable English deck, built by `build_pptx.py` |
| `abstract_EN.md` | English abstract |

## Videos

| File | Length | What it shows | By | Licence |
|---|---|---|---|---|
| [`videos/Synthetic_Tree_G_virtual_forest_sensors.mp4`](videos/Synthetic_Tree_G_virtual_forest_sensors.mp4) | 84 s, 1280×624 | The sensor platform driving its route through the virtual forest (v1, Isaac Sim). Top row: RGB camera, depth (0-40 m), segmentation; below: the LiDAR point cloud from above and from the side, coloured by class (ground, trunk, branch). 10 frames per second = real simulation time. Labels in Spanish. Made with `isaac_forest/run_sensors.py` and `isaac_forest/tools/make_video.py`. | Synthetic_Tree_G team | MIT, as the repository ([`LICENSE`](../LICENSE)) |
| [`videos/Synthetic_Tree_G_apple_pruning_robot_simulation.mp4`](videos/Synthetic_Tree_G_apple_pruning_robot_simulation.mp4) | 21 s, 1280×720 | Transfer to the orchard: a Franka Emika Panda arm in MuJoCo makes 5 of the 8 removal cuts that the language model NVIDIA Nemotron-3-Ultra-550B proposed for the real apple tree Bibaum A (pre-pruning TreeQSM of 2020, 659 cylinders; see [`apple/README.md`](../apple/README.md)). Platform 0.6 m from the row, 0.95 m high; the arm's path is checked for contact at every step; each removed part is highlighted, then taken off the tree. | Angel Marquez Aguilar | CC BY 4.0 |

Third-party parts seen in the videos: textures and HDRI sky from [Poly Haven](https://polyhaven.com) (CC0), rendered in
NVIDIA Isaac Sim; the Panda model from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie)
(`franka_emika_panda`, Apache-2.0), simulated with MuJoCo 3.14 (Apache-2.0) and the `mink` inverse-kinematics library.

## Using the videos

You may show, share, embed, cut, subtitle or translate both videos for any purpose, including teaching, talks,
papers and commercial work, provided you credit them:

- `Synthetic_Tree_G_virtual_forest_sensors.mp4`:
  > Virtual forest with simulated LiDAR and RGB-D camera, Synthetic_Tree_G team (Nelson Broyer-Paco, Angel
  > Marquez-Aguilar, Li Shi, Josine, Pacifique), https://github.com/Nosl3n/Synthetic_Tree_G, MIT licence.
- `Synthetic_Tree_G_apple_pruning_robot_simulation.mp4`:
  > Simulated pruning of the apple tree Bibaum A by Angel Marquez Aguilar, from Synthetic_Tree_G
  > (https://github.com/Nosl3n/Synthetic_Tree_G), licensed CC BY 4.0
  > (https://creativecommons.org/licenses/by/4.0/).

If you changed a video (cut, re-encoded with other settings, subtitled), say so next to the credit. In a paper, cite
the repository as [`CITATION.cff`](../CITATION.cff) describes.

Please keep two things clear when you show them:

- Both are **simulations**. The forest and its sensor data are synthetic; the pruning video is a robot simulation,
  not a field trial.
- The cuts in the pruning video are **a language model's proposal**, filmed to show that the arm can reach them.
  They are not a pruning recommendation and were not checked by a grower.

To download a video: open it on GitHub and use the download button (*Download raw file*).

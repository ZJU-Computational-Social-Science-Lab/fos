# generate_figures.py — entry point for the 7 final journal figures.
#
# What this file does: it regenerates the retained journal set (fig02,
# fig03, fig04, fig05, fig06, fig07_blinded, fig07_disclosed — each as
# PNG 300 dpi + vector PDF + plot-data CSV) from the corrected Stage 10
# data and the validated distributional results. The exploratory figures
# (fig01, fig08–fig11) were removed from the pipeline along with their
# output files; the git/project history holds the old code for recovery.
# All randomness is seeded (see fig_common.SEED), so repeated runs
# produce identical output.
#
# Functions:
#   main() -> runs fig02 (distributions) and effect figures 03–07

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_distributions import fig02_distributional_distance
import figures_effects


def main():
    print("== Figure 02 (distributional distance histogram, all 31, journal) ==")
    fig02_distributional_distance()
    print("== Figures 03–07 (effects, journal) ==")
    figures_effects.main()
    print("done: journal figures written to",
          Path(__file__).parent.parent / "figures")


if __name__ == "__main__":
    main()

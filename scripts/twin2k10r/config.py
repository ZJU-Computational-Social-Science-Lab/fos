# This file holds the study's fixed numbers in one place: where the local
# copy of the Twin-2K-500 dataset lives, the random seed everything uses
# (42), how many personas every run needs (100), and which persona
# configuration is the default (A = 7 real demographic fields only).
# Keeping them here means every module reads the same constants instead
# of each carrying its own copy that could drift apart.
from pathlib import Path

# The read-only local mirror of the Twin-2K-500 panel. Never copied into
# the repository; only ever read.
DATASET_ROOT = Path("/home/justin/work/datasets/Twin-2K-500")

# One seed controls the whole chain: sampling and (downstream) inference.
SEED = 42

# Every study cell uses the same pool size as the original twin2k10 study.
PERSONA_COUNT = 100

# The default persona configuration: "A" (7 real demographic fields).
# "B" additionally renders the 11 measured trait scores (robustness only).
POOL_CONFIG = "A"

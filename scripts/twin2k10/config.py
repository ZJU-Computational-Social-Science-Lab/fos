# This file holds every fixed knob of the twin2k10 study in one place: the
# 15 local models that run it (the same queue as the proven twin2k6 study,
# in the same order), the shipped survey-question file (a verbatim copy of
# the authoritative research delivery), how many personas answer, the
# inference settings copied from the proven R1 pipeline, the study's own
# thresholds (the 0.80 branch-mass flag, the at-most-50-records fsync
# promise), and twin2k10's own knobs: K=20 temperature samples per numeric
# answer and run names that start with "T2K10-". There are no functions
# here — only named constants so every other module and every test reads
# the same numbers from one source.

from pathlib import Path

# The proven R1 scoring pipeline already defines the one-in-a-million
# visibility floor for top-k entries; reuse it verbatim instead of copying
# the number (import works because twin2k10 is only ever imported with the
# repo's scripts/ folder on the import path).
from logprob_scoring import FOLD_PROBABILITY_FLOOR

# The study's name, used in run folders and output summaries. Distinct
# from twin2k6's so no output of the two studies can ever be confused.
STUDY_NAME = "TWIN2K_UNBLINDING_LOGPROBS_10TASKS"

# The repo root, found by walking up from this file (scripts/twin2k10/).
REPO_ROOT = Path(__file__).resolve().parents[2]

# The shipped survey-question file: a byte-for-byte copy of the
# authoritative research delivery
# (/home/justin/work/research/TWIN2K-UNBLIND-10TASKS/human_benchmark/
# stimuli.json). The study never reads the machine-specific research path;
# this shipped copy is verbatim and must never be edited.
STIMULI_PATH = REPO_ROOT / "data" / "configs" / "twin2k10_stimuli.json"

# The study's 15 models, in the pinned run order: exactly the local model
# queue of the twin2k6 study (which took it from the R1 registry,
# scripts/r1yesno_v2/registry.py, local_or_api="local"). The one API model
# (qwen3.8-max-0902) is deliberately excluded.
MODELS = [
    "gpt-oss-20b",
    "gemma-4-26b-a4b",
    "gemma-4-31b-it-qat",
    "gemma-4-12b-it-qat",
    "qwen3.8-27b",
    "qwen3.6-27b-dense",
    "qwen3.6-35b-a3b",
    "qwen3.6-35b-a3b-uncensored",
    "qwen3-32b",
    "qwen3-4b",
    "granite-4.1-8b",
    "granite-4.1-30b",
    "nemotron-cascade-2-30b-a3b",
    "muse-glimmer",
    "glm-4.7-flash",
]

# The two blinding arms, in run order: with and without the randomization
# note in the system prompt.
BLINDINGS = ("blinded", "unblinded")

# One shared pool of 100 personas (ids 0-99); every model answers the same
# pool so model differences are never persona differences.
PERSONA_COUNT = 100

# Inference knobs copied from the proven R1 first-token pipeline (same
# meanings as twin2k6's):
#   SCAN_TOKENS — the short generation window that lets the parser walk
#                 past control tokens to the first real answer token;
#   TEMPERATURE — the paper's fixed sampling temperature (also used for
#                 every numeric re-sample);
#   TOP_K       — how many top logprobs to request, big enough that all
#                 answer-letter spellings of the widest scale fit;
#   PROBABILITY_FLOOR — top-k entries below one in a million are sampler
#                 noise and never count as an answer (reused from R1).
SCAN_TOKENS = 8
TEMPERATURE = 1.0
TOP_K = 100
PROBABILITY_FLOOR = FOLD_PROBABILITY_FLOOR  # 1e-6, same number as R1

# A combined letter mass strictly below 0.80 is flagged "diffuse" — same
# stricter-than-R1 threshold the twin2k6 study used.
LOW_BRANCH_MASS_THRESHOLD = 0.80

# Numeric sampling: every numeric answer is measured K times at the study
# temperature and every parsed sample is stored, so the spread of a
# model's numeric answers is visible, not just one draw.
NUMERIC_SAMPLES_K = 20

# How many tokens a numeric sample call may generate before it is cut
# off. 128 fits even a bare 10-row multi-row answer (~50 tokens with no
# prose) with comfortable headroom, so a truncation in the stored
# samples means the model stopped early — never that the window cut it.
NUMERIC_MAX_TOKENS = 128

# Durability promise: the records file is force-synced to disk at least
# this often, so a crash can lose at most 50 finished records.
FSYNC_EVERY = 50

# The design seed shared by every run of this study.
SEED = 42

# Run folders start with this prefix (results/unblinding/T2K10-<stamp>/)
# so they can never collide with twin2k6 run folders.
RUN_NAME_PREFIX = "T2K10-"

# The live smoke test (--smoke) runs ONE small model on ONE persona
# through the whole 19-arm x 2-blinding grid, so a pre-launch check
# costs minutes instead of days. Its run folders start with their own
# prefix (results/unblinding/T2K10-SMOKE-<stamp>/) so a smoke run can
# never be mistaken for — or appended onto — a production run folder.
SMOKE_MODEL = "qwen3-4b"
SMOKE_PERSONA_ID = 0
SMOKE_RUN_NAME_PREFIX = "T2K10-SMOKE-"

# Where run folders are created, relative to the repo root.
RUNS_ROOT = REPO_ROOT / "results" / "unblinding"

# Where the local model server and its model manager live (same defaults
# as every R1 run: llama-server on 8080, the manager control API on 8081).
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_MANAGER_URL = "http://127.0.0.1:8081"

# This folder holds the TWIN2K_UNBLINDING_LOGPROBS_10TASKS study package:
# the ten Twin2K survey experiments (23 questions) are put to 15 local
# language models, each once with and once without the "which version was
# randomized" note; choice answers are scored from the first answer
# token's letter probabilities, numeric answers are sampled K=20 times
# and parsed, and results are compared against the human benchmark
# numbers. Import it as `twin2k10.<module>` with the repo's scripts/
# folder on the import path (same convention as the other launch
# scripts). The sub-modules are:
#   config      — the study's fixed knobs (models, files, K, thresholds)
#   registry    — the model address book (manager ids, GGUF paths)
#   experiments — the ten experiments, their arms and question ids
#   prompts     — builds the exact system and user prompt texts
#   scoring     — letter folding, parse_numeric, parse_multi_numeric
#   cells       — the 57,000 (model, persona, arm, blinding) cells + resume
#   numerics    — the K=20 temperature-sample calls for numeric answers
#   legexec     — executes one cell end to end into its record
#   preflight   — the pure stop-or-proceed verdict + report writer
#   runner      — the single-command launch (auto-preflight, resume)

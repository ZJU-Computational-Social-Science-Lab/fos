# RUNNER_IMPLEMENTATION_REPORT.md — Task 3139 (production runner)

**Status:** runner COMPLETE, tests GREEN, live smoke GREEN, parity replay FAIL → **production NOT launched** (launch gate 2 of 3 failed).

## What was built

Package `scripts/twin2k10r/integration/production/` (all files < 500 lines,
plain-language headers, ruff clean):

| File | Purpose |
|---|---|
| `model_ids.py` | Reconciled record-id → server-id map (Task 3137): 6 exact matches, 9 NAME-DRIFT-SAME-WEIGHTS, granite-4.1-30b trap pinned to `lmstudio-community` (Q4_K_M). `server_model_id()` raises `UnknownModelError` on a typo. |
| `run_plan.py` | The merged 31-experiment grid: 8 twin2k10r in-grid + 6 restored (twin driver) + 17 T2KX (expansion driver). Model queue = historical order with muse-glimmer + glm-4.7-flash (flagged) last. |
| `prompts_twin.py` | Twin-driver prompts: pinned twin2k10r scaffold, real-field persona blocks, restored-experiment item splitting (MC/TE normalized via `response_kind()`), unblinded disclosure = design+versions only. |
| `cells_twin.py` | One twin cell end-to-end: one first-token call per item (choice scorer / digit scorer with 16-token window), scoring reused from frozen `legexec`, provenance-stamped record (`run_id`, `dataset_sha256`, `persona_id`/`pid`, `prompt_sha256`, `status` ok/failed). |
| `driver_twin.py` | Twin legs: cells = persona × arm per (experiment, blinding); per-record flush+fsync; torn-tail repair; resume by the frozen 5-part record key — never duplicates. |
| `driver_expansion.py` | T2KX legs through the frozen expansion pipeline (read-only import): pipeline record shape + prompts + scoring, bounded retry, resume by (persona, condition, item_index). |
| `serving_prod.py` | Direct llama-server on 8080: frozen serve table + flags (`--reasoning off`, `--skip-chat-parsing`, jinja templates), `setsid` own-session launch, atomic pidfile, health wait, identity check, canary. |
| `parity_replay.py` | Launch-gate check: replays one archived record's exact prompt and compares the first-token top-1. |
| `safeguards.py` | Circuit breaker (5 consecutive failures → `CircuitOpenError`), disk floor, PID file, atomic JSON, PROGRESS.json. |
| `production_runner.py` | The single command: pools → manifest → per-model blocks (twin legs then expansion legs, one model loaded at a time). Modes: production / `--smoke` / `--dry-run` / `--run-dir` resume. |

Pool policy: the canonical hash-pinned Stage 0 Config A pool
(`bdc84233…eea1`, the same 100 respondents everywhere) is reused verbatim
and sha256-verified before every launch; personas are never regenerated
mid-run. The expansion adapter (`expansion_pool.write_adapted_pool`)
produces the legacy-field copy for T2KX legs.

## Tests (TDD: written first, all RED before implementation)

`tests/test_twin2k10r_production_3139.py` — 12 tests against a mock
llama-server (localhost HTTP: /health, /v1/models, /v1/chat/completions
with canned top-logprobs):

1. reconciled id for qwen3-4b (`qwen/qwen3-4b-2507`)
2. exact matches + granite trap + unknown-model refusal
3. flagged models last, clean order preserved
4. merged 31-grid coverage (14 twin + 17 expansion)
5. twin leg vs mock server (cell iteration, 4 records for disease)
6. provenance on every record + both blinding arms' system prompts differ
7. digit scoring (sunk_cost TE → digit_items with p_norm)
8. resume: zero new calls, zero duplicates
9. torn tail re-runs exactly the torn cell
10. expansion leg vs mock server with adapted pool (100 records)
11. circuit breaker opens at cap
12. circuit breaker resets on success

`verify-tdd.sh` gates 1–3: **PASS** (12 passed; test files unchanged; count 3024).

Existing suites re-run after implementation (no regressions in the study
code): `tests/twin2k10r` 121 passed; twin2k10 core suites 90 passed.

## Live smoke (real llama-server, port 8080, qwen3-4b reconciled id)

Run `extended_run-SMOKE-20261103T144353/` (worktree root):

- pool reused (sha256 verified) → manifest + PID file written
- llama-server launched (pid 93818), identity check passed (served the
  exact Qwen3-4B-Instruct-2507-Q8_0.gguf), canary `OK`
- twin pipeline × both arms × BOTH scoring types: disease (choice) and
  sunk_cost (digit), blinded+unblinded — 16 records, all `status=ok`
- expansion pipeline × both arms: T2KX-ml1_gamblers_fallacy blinded+
  unblinded — 8 records, all `status=ok`, provenance stamped
- both arms produced distinct system prompts; first-token logprobs scored

## Parity replay — FAIL (the launch gate stops here)

Archived record: `T2KX-20261022T222604/qwen3-4b/T2KX-ml1_gamblers_fallacy_blinded/records.jsonl` line 0 (persona 0, gambler_two_sixes).

| | Stored (8080, run era) | Fresh (8080, frozen flags) |
|---|---|---|
| top-1 | **C** (−0.130) | **B** (−0.719), C second (−0.814) |
| top-5 | C, A, B, D, E | B, C, D, E, A |

Root cause found and verified: this session has **no GPU device nodes**
(`/dev/dri` missing; `mknod` denied). llama-server logs
`warning: no usable GPU found --gpu-layers ignored` and falls back to
CPU; the historical runs served on
`Vulkan0 : AMD Radeon 8060S (RADV STRIX_HALO)`. Probe without KV-cache
quantization (`--cache-type-* q4_0` dropped, flash-attn off) still gives
A (−0.55) — CPU numerics, not the KV flags, move the distribution. The
llama.cpp source is the same commit as the run era (3931e17); the binary
is fine — the *device* is the problem.

Because fresh top-1 ≠ stored top-1, gate "parity replay matches" fails.
Per the task contract: **STOP and report, no production.**

## How to run once a GPU-visible session exists

```bash
# 1. gate checks (inside the repo worktree)
python scripts/twin2k10r/integration/production/production_runner.py --smoke
python - <<'P'   # parity replay must print "match": true
...  # see parity_replay.py docstring; run parity_replay.replay_record
P
# 2. production (EXTENDED_RUN_ROOT chooses the output root; the default
#    planned /home/justin/work/ is read-only on this machine)
EXTENDED_RUN_ROOT=<writable root> \
  setsid nohup python scripts/twin2k10r/integration/production/production_runner.py \
    > /tmp/extended_run.out 2>&1 &
# monitor: tail -f <run-dir>/PROGRESS.json   (rewritten atomically)
# stop:    kill $(cat <run-dir>/runner.pid)  (llama-server pid: /tmp/t2kx-llama-server.pid)
# resume:  python ... production_runner.py --run-dir <run-dir>
```

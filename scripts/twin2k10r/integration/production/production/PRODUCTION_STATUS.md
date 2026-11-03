# PRODUCTION_STATUS.md — Task 3139 (extended production run)

**STATE: NOT LAUNCHED — launch gate FAILED at parity replay.**

## Launch gate checklist

| Gate | Result |
|---|---|
| 1. Tests GREEN (existing + new) | **PASS** — 12 new mock-server tests + verify-tdd gates 1–3; twin2k10r suite 121, twin2k10 core 90, no regressions in study code |
| 2. Parity replay matches | **FAIL** — stored top-1 `C` vs fresh `B` (see below) |
| 3. 8080 healthy | **PASS** — direct llama-server (frozen flags) healthy on 8080, identity check + canary OK |

## Why the parity gate fails (evidence)

- Replay of archived record
  `T2KX-20261022T222604/qwen3-4b/T2KX-ml1_gamblers_fallacy_blinded/records.jsonl`
  (line 0) with frozen flags on restored port 8080:
  stored top-1 **C** (−0.130) vs fresh top-1 **B** (−0.719, C −0.814 second).
- Server log shows `no usable GPU found — --gpu-layers ignored`: this
  session has no `/dev/dri` device nodes (mknod denied), so llama.cpp
  falls back to CPU. Historical runs served on Vulkan RADV
  (`AMD Radeon 8060S`, see `~/fos-model-manager/llama-server-8080.log`).
- Control probe WITHOUT KV-cache quantization still gives A (−0.55) —
  CPU-vs-iGPU numerics, not the KV flags, shift the first-token
  distribution. Same llama.cpp commit as the run era (3931e17).

## Launch command (run ONLY after parity passes in a GPU-visible session)

```bash
cd /home/justin/work/worktrees/implement-3139   # writable worktree
EXTENDED_RUN_ROOT=/home/justin/work   # once that mount is writable; else any writable root
setsid nohup python scripts/twin2k10r/integration/production/production_runner.py \
  > /tmp/extended_run.out 2>&1 &
```

- Run dir created at `$EXTENDED_RUN_ROOT/extended_run-<UTCstamp>/`
  (default root: this worktree, because `/home/justin/work` is a
  read-only mount on this machine — deviation from the task text).
- Config A pool sha256-verified against the pinned Stage 0 pool; same
  100 respondents everywhere; sequential; flagged models last.

## Monitor / stop / resume

```bash
tail -f <run-dir>/PROGRESS.json        # atomic snapshots
tail -f /tmp/extended_run.out          # runner log
cat <run-dir>/runner.pid               # runner pid
cat /tmp/t2kx-llama-server.pid         # current llama-server pid (pidfile json)
# stop both:
kill $(python -c "import json;print(json.load(open('<run-dir>/runner.pid'))['pid'])")
kill $(python -c "import json;print(json.load(open('/tmp/t2kx-llama-server.pid'))['pid'])")
# resume (never duplicates finished records):
python scripts/twin2k10r/integration/production/production_runner.py --run-dir <run-dir>
```

## Deliverables

- Smoke run (GREEN, offline-inspectable): `extended_run-SMOKE-20261103T144353/`
  at the worktree root — both pipelines × both arms × both scoring types,
  24 records, all `status=ok`.
- Implementation report: `RUNNER_IMPLEMENTATION_REPORT.md` (same dir).
- No production records exist; nothing was written into any frozen run.

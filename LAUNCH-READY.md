# LAUNCH-READY — Gui & Toubia replication sweep, 21:30 full-study run

Status: **pre-flight done — ✅ persona-pool blocker RESOLVED (TASK-1521)**.
The launch wrapper (`scripts/launch_grid.py` + `launch_support.py`
+ `launch_sweep.py`) is ready and the post-fix smoke pre-flight passed the
full persona path: model load via the manager, the paper-CSV persona draw
PARSED (pool sample written, `persona_parsed: true`), file write-through.
`parse_persona` now accepts the Prompt 10 comma-separated completion as
well as the old underscore-key label shape. **The 21:30 run has NOT been
started — decide below before starting it.**

---

## ⚠️ Persona-pool blocker (discovered by the pre-flight smoke)

The persona-pool phase of the R1 profile cannot complete with the current
tooling, and this is a format mismatch, not a model problem. Smoke evidence
(this afternoon, nemotron Q8, 4/4 draws):

    42, female, master's degree, 62000, marketing manager, Hispanic, single, 4, 2, TX, rent, 4.99, purchase
    32, female, bachelor's degree, 45000, teacher, White, married, 4, 2, TX, rent, 3.49, purchase

Those are **exactly the paper's requested CSV return format** (the persona
prompt's own "Return example" line) and they are **rejected** by
`fos.experiments.personas.parse_persona`, which only parses lines labelled
with the internal keys (`household_income:`, `marital_status:`, ...) that
no instruction ever asks the model to produce. The parser's canned test
fixture uses exactly that key shape (tests/test_personas.py `_CANNED_RAW`),
so the tests pass while real runs cannot. Offline proof: the parser also
rejects the prompt's completed-block shape ("Education level: college") and
the prompt's own CSV line. In short: prompt (paper labels + CSV example) and
parser (internal keys) disagree; this is a pipeline bug from the task-1491
drift fix that no post-drift persona pool has ever exercised.

Consequences for the wrapper:
- Pool generation would draw every persona as "skipped"; after top-up
  rounds the wrapper fails the pool phase loudly (exit 3, message lists the
  short products). No silent/partial data. But ~3 h would be wasted.
- Fixing `parse_persona` (accept the paper CSV shape / paper labels) is a
  small implement task with additive tests — NOT done here (wrapper task,
  tooling semantics locked). It needs a test-side re-spec/approval.

### Options for 21:30 (user decision)
1. **Fix first, then launch** (recommended): dispatch the small
   parser-alignment task, re-run the smoke (one command, ~1 min GPU), then
   launch R1 as designed. Cleanest science; ~30-45 min slip.
2. **Run plain-depth only tonight** (depth `none`, no personas needed):
   use the existing tool directly, 4 legs would not apply — one command:
   ```bash
   cd "/home/justin/Documents/ZJU work/fos"
   nohup python3 scripts/unblinding_sweep.py --model nvidia/nemotron-cascade-2-30b-a3b \
     --base-url http://127.0.0.1:8080 --manager-url http://127.0.0.1:8081 \
     --manager-port 8080 --blinding both --persona-depth none --draws 50 \
     --out results/unblinding/plain-only-2130 > /tmp/plain_only_2130.log 2>&1 &
   ```
   (~44,000 calls at ~0.65 s/call, single client = ~8 h sequential; for
   a night fit use `--draws 10` instead = 8,800 calls ≈ 1.6 h, the
   pilot's plain-tier suggestion). This drops the demographics comparison
   for tonight.
3. **Postpone the full R1** until the parser fix lands.

## One command (21:30, recommended profile R1, once the blocker is cleared)

```bash
cd "/home/justin/Documents/ZJU work/fos"        # main checkout, after task/1517 is merged

nohup python3 scripts/launch_grid.py --profile R1 \
  --run-name r1-20260908T2130 \
  --progress-every 2500 \
  > /tmp/r1_2130.log 2>&1 &

tail -f /tmp/r1_2130.log
```

That is the whole run: it loads the model through the manager, generates
the persona pools, and runs the four sweep legs. A live progress line
(`done/total calls, parse rate so far, ETA`) prints roughly every 2,500
calls (~7–9 min).

Pre-flight sanity check first (read-only, safe any time):
`python3 scripts/launch_grid.py --dry-run --profile R1`.

## What it runs (profile R1)

- Model: `nvidia/nemotron-cascade-2-30b-a3b` (Q8) on **port 8080** via the
  model manager (`POST :8081/models/load`).
- 40 products (Table A.1) x 11 price levels (0–200% in 20% steps).
- Depths `none` (plain survey, 50 draws/cell) and `demographics` (11-field
  persona, **K = 100** personas/product, uniform-random subsample of the
  pool with pool-seed **42**).
- Both blindings (`blinded`, `unblinded`).
- Call budget: **132,000 sweep calls** (4 legs) + ~4,800 persona-pool draws
  (requested; accepted ~95%+, subsampled to exactly K=100/product).
- The four (depth x blinding) legs run **concurrently** so the llama-server's
  four slots stay busy (measured pilot speedup 3.7x).

## Expected duration (from measured pilot latencies, RESULT-1501)

| Phase | Wall time |
|---|---|
| Persona pools (40 x ~120 draws, ~2 s/draw, sequential) | ~2.7 h |
| Sweep legs, 4-way concurrent (~0.65–0.8 s/call / 3.7x) | ~6.4–7.4 h |
| **Total** | **~9–10 h** → done ~06:30–07:30 |

Persona-leg calls prefill longer surveys, so treat the upper bound as the
planning number. Sequential single-slot would be ~24 h — do not run it
single-threaded.

## Output locations

Everything lands under **`results/unblinding/<run-name>/`** in the checkout
you launch from (git-ignored; the pilot backups copy `results/` to
`~/work/fos-data/results/` after each phase):

- `manifest.json` — run-level record: profile, K, pool-seed, model, commit
  sha, started/ended, planned vs actual calls, per-leg parse rates.
- `pools.json` + `pools/` — the K=100/product pools (seed 42) and their
  generation summary.
- `none_blinded/`, `none_unblinded/`, `demographics_blinded/`,
  `demographics_unblinded/` — each leg's `<model>_<blinding>.jsonl/.csv`
  + its own `manifest.json` (design, prompts' sha, timestamps, pool-seed).

## Stopping the run (graceful stop / hard stop — TASK-1533, cell-granular)

The wrapper installs SIGINT and SIGTERM handlers while a real run is
active. Because every completed cell is appended to the leg's jsonl and
flushed the instant it finishes (cell-granular durability, TASK-1533), a
stop at any time keeps every finished cell and loses at most the ONE
in-flight call.

- **How to stop** — from the run's console press `Ctrl-C` once, or from
  another shell `kill -INT <wrapper-pid>` (equivalently `kill -TERM`). The
  wrapper prints `graceful stop requested — finishing current leg(s), N
  calls remaining in flight`, then every running leg pauses at its NEXT
  cell boundary (each finished cell is already durable on disk — nothing
  is lost), does not start any leg that had not begun, and writes
  `manifest.json` with `state: "stopped_gracefully"` plus each planned
  leg's completion status. Exit code is 0 (clean operator-requested stop).
  A stop requested during model load or pool generation lands at the next
  wrapper boundary (the current model-load call or pool invocation
  completes first — pools keep every accepted persona, so `--resume` later
  tops up only what is short).
- **Escalate** — send a SECOND signal (or launch with `--force`): the
  wrapper hard-stops immediately — the shared abort fires and every
  in-flight leg stops at its next cell. Finished cells are kept; a later
  `--resume` executes only the cells that were never completed. Exit code 1.
- **`--force`** — launch with `--force` to make even the FIRST signal an
  immediate hard stop (skip the graceful wait entirely).
- **When it is safe** — always: every completed cell is flushed to disk as
  it finishes, so graceful AND hard stops (and even a SIGKILL) lose at most
  the single in-flight call, which `--resume` re-runs exactly once.
- **Progress file** — while legs run, `<run>/progress.json` is rewritten
  (atomically) at most every ~5 s: `cells_done`, `cells_total`,
  `per_leg: {done, total}`, `calls_per_sec_measured`, `eta_seconds`,
  `parse_rate_so_far`, `updated_at`. On a resume the durable counts are
  seeded from disk, so progress is monotonic across restarts.
- **After a stop**, resume with the same `--resume` command below — it
  plans exactly the legs that never finished and executes only the cells
  that were never completed; the final manifest reaches `state: "complete"`.

## Crash / resume behaviour (verified end-to-end, TASK-1522/1533)

- **The run is marked as started immediately**: the run-level `manifest.json`
  is written (`state: "running"`) as soon as the run begins, so an
  interrupted run is recognised and its true start time survives. Re-running
  the exact same command WITHOUT `--resume` into a directory that already
  holds a manifest, `pools.json`, or leg files is refused with exit 2
  (pass `--resume`, pick a new `--run-name`, or delete the directory).
- **Model load** is skipped on resume when the manager already serves the
  right model on the port.
- **Persona pools** append every accepted persona as they are drawn, so a
  killed pool phase keeps its progress; rerunning tops up only the products
  that have fewer than K accepted personas (never re-draws finished ones).
  The pool phase is skipped entirely once `pools.json` matches (K, seed,
  model, product count).
- **Sweep legs are cell-granular (TASK-1533)**: each completed cell's
  record is appended to `<run>/<depth>_<blinding>/<model>_<blinding>.jsonl`
  and flushed the moment it finishes (fsync every 64 records and at leg
  end/stop), so a crash at any instant loses at most the ONE in-flight
  call. Rerun the exact same command with `--resume`:
  ```bash
  python3 scripts/launch_grid.py --profile R1 --run-name r1-20260908T2130 --resume
  ```
  The resume planner counts the leg's own records file and skips exactly
  the cells already durably done — no cell is executed twice and none is
  skipped. Completed legs are skipped exactly once; the leg's csv/manifest
  are written only when the whole leg has completed. The FINAL
  `manifest.json` lists every planned leg exactly once, keeps the earliest
  start, carries the pools summary forward, and records each resume under
  `"resumed"` — resuming a fully completed run is a safe no-op that never
  wipes the manifest.
- **Watchdog:** if the chat server dies (see the pinning risk below) the
  run aborts within ~90 s instead of recording silent failures. Rerun with
  `--resume` after the cause is fixed.

## ⚠️ Model-pinning risk (read before 21:30)

The pilot recorded an **external actor (another pi session on this machine)
restarting `:8082` mid-pilot** (3x). The manager's `/models/load` and
`/switch` endpoints **kill the llama-server on the target port and reload**,
so any session that issues a switch while our run is active kills our server
mid-run. The watchdog catches it (abort + resume), but an avoidable
interruption costs hours.

- **Pin the overnight run to `:8080`** (default). Load only
  `nvidia/nemotron-cascade-2-30b-a3b` on it, once, through this wrapper.
- **Close or pause other pi/llama sessions that control the manager**
  (they must not issue `/models/load`, `/switch`, or `/models/unload`).
- Do **not** use `:8082` for anything tonight (muse is behaviourally
  excluded from the study and is the port the external actor cycles). The
  wrapper accepts `--port 8082` only for a future second-model leg — not
  tonight.
- Leave LM Studio (`:1234`) untouched; the manager does not control it.
- If a second task genuinely needs GPU tonight, it must run on `:8082`
  with a **different model** and accept that our run never touches it.

## FULL profile (paper n, for the record — NOT tonight's command)

```bash
python3 scripts/launch_grid.py --profile FULL --i-know-this-is-41h
```

K=500 personas/product. Under the tooling's real loop semantics the run is
~484,000 sweep calls + ~24,000 pool draws → **~23–29 h batched sweep +
~13 h pools ≈ 37–42 h**. The pilot's measured full-grid figure (RESULT-1501)
for the 880,000-call grid at 4-slot batching was **~41–45 h**. FULL needs a
multi-day uninterrupted window, not a night, and refuses to start without
`--i-know-this-is-41h`.

## The decision you own (one line each)

- **R1** — fits the night (~9–10 h from 21:30); per-cell CI ±0.10 at
  K=100, 40-product pooled curve ±0.016; the defensible overnight choice.
- **FULL** — the paper's n=500 (~38–42 h batched); only if a multi-day
  uninterrupted GPU window is acceptable — not tonight.

## Files

- `scripts/launch_grid.py` — entry point (flags, plan, dry-run, smoke, run).
- `scripts/launch_support.py` — model manager calls + persona-pool
  generation/subsampling.
- `scripts/launch_sweep.py` — concurrent sweep legs, watchdog, manifests,
  smoke pre-flight.
- Existing tooling (`scripts/unblinding_sweep.py`,
  `scripts/generate_personas.py`) is invoked unmodified.

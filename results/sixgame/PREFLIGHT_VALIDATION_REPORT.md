# PREFLIGHT VALIDATION REPORT — Mandatory pre-execution validation gate (TASK-2734)

**Status: COMPLETE (offline — zero network calls, zero paid API calls)**
Worktree: `/home/justin/work/worktrees/implement-2734` (branch `task/2734`)
Scope: engineering pilot, model `deepseek-v4-flash`, 180 decisions + 60 probes = 240 observations.

---

## 1. Root cause: where the persona text was lost (pre-fix runner)

**The loss point.** In the pre-fix runner (commit `0fa66c0`, file
`scripts/sixgame/runner.py`, `run_plan`, ~line 366 of that revision), the
persona text was loaded with no arm check:

```python
persona_file = personas_dir / f"{sample.persona_id}.txt"
persona_text = (
    persona_file.read_text(encoding="utf-8") if persona_file.exists() else None
)
```

Two independent defects sat on these three lines:

1. **Arm-blind loading.** `persona_text_for()` (added in the fix, commit
   `eadad82`, merge of task/2726) now returns `None` for every
   `no_persona` sample. Pre-fix, the no_persona arm received the full
   biography — had the file existed. The arm contrast would have been
   destroyed in the *other* direction (both arms treated).
2. **Silent fallback to None.** `persona_file.exists()` was checked
   against `personas_dir = Path(".")` — the *current working directory*
   of the runner process. The original run was launched from a directory
   that did not contain the `personas/*.txt` files, so `exists()` was
   False and **both** arms silently got `persona_text=None` (the
   name-only placebo). No error, no log — the `if not persona_names`
   guard only covered the CSV, not the txt files.

This explains RESULT-2727's prompt-hash reconstruction exactly: 100% of
checked original-run cells matched the name-only placebo prompt
byte-for-byte in BOTH arms — the run was a no-persona run wearing a
two-arm costume. The failure hit both arms because there was a single,
arm-blind, silently-degradable load site feeding both.

**Why 92 green tests missed it.** The test suite (68 tests at the time
of the original pipeline commit `e648019`, 92 after task/2726) exercised
`build_decision_prompt(sample, persona_text, ...)` with `persona_text`
supplied *as a parameter* — the tests constructed prompts directly and
asserted on their content, so loading worked and the prompts contained
biographies. No test executed `run_plan` end-to-end against a real
directory layout and asserted that a persona-arm *record's* prompt hash
differs from its no_persona twin's. The unit of testing (prompt builder,
pure function) was one level below the unit that failed (file resolution
inside the run loop). The fix's own tests (`tests/sixgame/test_fix_2726.py`)
closed exactly this gap; TASK-2734 closes it permanently at runtime.

**Fix reference.** Commit `eadad82` (task/2726): `persona_text_for()`
returns None unconditionally for the no_persona arm and reads the file
for the persona arm; `tests/sixgame/test_fix_2726.py` locks the contract.

---

## 2. The runtime preflight gate

New module `scripts/sixgame/preflight.py`, CLI
`python -m sixgame.preflight --config … --model … [--run-dir]`.

Before its first real send, the runner (`--config` path in `main`) now
rebuilds every planned prompt and asserts, offline:

- **Persona arm**: the identity section equals the persona file byte-for-byte
  (biography fingerprint = sha256 of the persona text) and contains ≥3
  distinctive biography spot-check words (presence only — **no biography
  content is ever printed**). A missing persona file is a hard failure
  (the original silent-None is now impossible to run).
- **No-persona arm**: identity section is exactly the name-only placebo
  (`You are {persona_id}.`); contains NO biography spot-check words.
- **Arm pairs** differ ONLY in the identity section (everything from
  SECTION 2 on byte-identical; for dieroll the per-arm seeded true roll
  is normalized before diffing; for pms each arm must carry its own
  seeded Row/Column assignment — both randomizations are per-arm by
  frozen design).
- **Die rolls**: every dieroll prompt carries the harness's seeded true
  roll (`draw_true_roll`), 1–6.
- **Probes**: question stem present, correct rung description present,
  no matrix role.
- **Plan shape**: per-cell counts, models, variants, arms, personas and
  draw numbering match the frozen config (180 decisions + 60 probes for
  the deepseek engineering pilot).
- **Captured requests** (`--run-dir` / post-run in `--dry-transport`):
  every serialized body matches a planned prompt byte-for-byte,
  temperature exactly 1.0, each planned prompt sent exactly as many
  times as planned.

**Gate semantics.** `runner.main` calls `run_preflight` before the first
send and exits non-zero (code 2) with a reason per failure. Opt-out
`--skip-preflight` exists for tests only. `--dry-transport` executes the
full plan against an offline mock transport (`sixgame.transport.dry_transport`,
route `"dry"` — canned 200 chat-completions body, no network, no
credentials), captures every serialized payload to
`<out-dir>/captured_requests.jsonl`, and re-verifies the captured bodies
against the plan after the run (exit 3 on mismatch).

---

## 3. Full offline dry run — 240/240 PASS

Command (production runner, mocked transport):

```
PYTHONPATH=scripts python3 -m sixgame.runner \
  --config scripts/sixgame/configs/engineering_pilot.yaml \
  --model deepseek-v4-flash \
  --personas-dir <repo>/personas \
  --personas-csv <repo>/final_200_personas.csv \
  --out-dir results/sixgame/dryrun_gate --dry-transport
```

Result: `{"completed": 240, "skipped": 0, "failed": 0}`; preflight green
before the run (240 planned requests checked) and green after
(240 captured requests match the planned prompts, temperature 1.0).
Artifacts in `results/sixgame/dryrun_gate/`: 30 per-cell JSONL files
(180 decision + 60 probe records, all `succeeded=true`, all
`finish_reason=stop`), `captured_requests.jsonl` (240 bodies),
`cache_audit_2734.jsonl`.

Per-cell summary (240 samples; every row PASS on all checks; full table
in `dryrun_gate/cell_table.md`):

| namespace | game | variants | arms | n | checks |
|---|---|---|---|---|---|
| decisions | 1120 | basic, cycle, r31-40 | persona, no_persona | 60 | PASS |
| decisions | dieroll | private, public, stake10 | persona, no_persona | 60 | PASS |
| decisions | pms | G1, G4, relabel | persona, no_persona | 60 | PASS |
| probes | 1120 | r11-20, r31-40 | persona, no_persona | 20 | PASS |
| probes | dieroll | private, public | persona, no_persona | 20 | PASS |
| probes | pms | G1, G4 | persona, no_persona | 20 | PASS |

**Refusal demonstration (corrupted config).** With a deliberately
corrupted config (`draws_per_cell: 7`, variant `typo-variant`), the
runner refused to start:

```
PREFLIGHT FAIL: plan has 126 decisions, expected 180   (count mismatch)
PREFLIGHT FAIL: decisions/1120/typo-variant/persona …: prompt build
                refused: unknown 11-20 variant: 'typo-variant'
preflight gate: N failure(s) — run refused   → exit code 2, zero sends
```

---

## 4. Cache audit — the 24 response-cache exclusions

Scope: the 24 legacy `cache_status=HIT` records in the 9 retained
persona-arm decision files of the original run (`engineering_pilot/`),
which are exactly the 24 exclusions reported by the corrective analysis
(`engineering_pilot_corrective/reports/analysis.json`: `"cache_hit": 24`).

**Evidence basis.** Legacy records store `cache_status` only (the pre-fix
runner set HIT solely from `usage.prompt_cache_hit_tokens > 0`), plus
`prompt_tokens`, `completion_tokens` and the full completion text. The
usage detail fields are NOT retained verbatim on the records — the audit
therefore reconstructs evidence from (a) the recorded HIT flag's proven
derivation from `prompt_cache_hit_tokens` (pre-fix `record_for`), and
(b) completion-content comparison across all same-`prompt_hash` peers
(the two-arm design shares prompt hashes across arms and draws).

**Verdict: all 24/24 — prompt-prefix (context) caching, completion
freshly sampled.** Every one of the 24 records has peers with the same
prompt hash, and every peer completion differs (distinct
`raw_content`, distinct `completion_sha256`). Identical completions for
identical prompts — the signature of a reused completion body — appear
0 times. At temperature 1.0 with thousands of completion tokens
(e.g. 9,486; 8,437), byte-distinct completions are only consistent with
fresh sampling behind DeepSeek's automatic prompt-prefix cache.

**Should the exclusions be reclassified?** The exclusions are *justified
under the frozen legacy rule* that the corrective analysis applied to
records lacking `cache_kind`; but the evidence supports reclassifying all
24 as context-cached (kept) under the current ANALYSIS_PLAN rule. Any
reclassification changes analysis inputs and must go through the
orchestrator/user — nothing was changed here. Per-record verdicts:
`dryrun_gate/cache_audit_2734.jsonl`. **Documented limit:** without the
raw per-record `prompt_cache_hit_tokens` values (not persisted by the
legacy runner), the HIT flag's derivation is established from code, not
from stored fields.

---

## 5. Provenance separation — VERIFIED

- Original dirs (`results/sixgame/engineering_pilot/`,
  `results/sixgame/engineering_pilot_corrective/` at the main repo) were
  hashed (per-file sha256 tree hash + mtimes) **before and after** all
  work: **identical** (`7b1a9f30…` both times). Untouched.
- Dry-run artifacts live in a separate directory
  (`results/sixgame/dryrun_gate/` in the worktree), excluded from
  analysis inputs.
- Repaired probe files remain parallel (`engineering_pilot/repaired/`),
  run IDs `engineering_pilot` vs `engineering_pilot_corrective` remain
  separate; no cross-contamination.

---

## 6. Prepared 1-observation paid validation (NOT executed)

Ready command — one persona-arm observation (1120/basic, persona #1)
through the full production path (real direct DeepSeek route, preflight
gate active):

```
PYTHONPATH=scripts python3 -m sixgame.runner \
  --config scripts/sixgame/configs/engineering_pilot.yaml \
  --model deepseek-v4-flash --game 1120 --variant basic --arm persona \
  --personas 1 --draws 1 --limit 1 \
  --personas-dir <repo>/personas \
  --personas-csv <repo>/final_200_personas.csv \
  --out-dir results/sixgame/paid_validation_1obs
```

Preflight status for this sliced plan: **OK (1 planned request checked)**
— the sample resolves a real persona file (clumsybassdropper#0),
carries the full biography fingerprint, temperature 1.0, direct route.
**Execution awaits user approval; if approved and valid it counts toward
the frozen 120 persona-corrective calls.** (The new `--limit` flag slices
the plan; it changes nothing else.)

---

## 7. Test results

- `pytest tests/sixgame/ -q` → **92 passed** (no test file created or
  modified by this task; the gate is demonstrated via CLI runs above).
- Full suite: see RESULT-2734 (recorded at execution time).

*No private biography content appears verbatim anywhere in this report
or in any artifact; only fingerprints (sha256 prefixes) and presence
booleans.*

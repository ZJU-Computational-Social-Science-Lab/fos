# PROJECT RESTART AUDIT — Six-Game LLM Behavioural Transfer Experiment

**Date:** 2026-10-16 · **Scope:** investigation only (no code changed, no API calls made)
**Sources:** repo audit (RESULT-2664), Cloudflare docs research (RESULT-2665), live Cloudflare token check.
Full evidence files: `~/work/crew/research/OUTBOX/RESULT-2664.md`, `~/work/crew/research/OUTBOX/RESULT-2665.md`.
Facts are marked **[F]** (file/line or doc-quotable); inferences **[I]**.

---

## 1. Executive summary

The project asks whether LLMs playing classic behavioural-economics games (a) **replicate** published human responses to rule changes and (b) **stay consistent** when the game is transformed in structure-preserving ways. After ~6 weeks parked, the state is:

- **Implemented and run (exploratory only):** the **11–20 money-request game** (conditions incl. 31–40 range-shift and inverted-payoff variants) and the **die-roll honesty task** (2 prompt variants), across 3 models (deepseek-v4-flash, claude-sonnet-5, gpt-5.6-luna) × 20 Reddit personas, **temperature 0, single-shot**, via OpenRouter (Claude/GPT) and DeepSeek direct. All result files date 2026-09-01/02.
- **Not implemented:** matrix/3×3 games, the remaining 4 of 5 transformation rungs, recognition probes, temperature-1 multi-draw mode, any statistics pipeline, any preregistration.
- **Pilot verdict:** the current code **cannot execute the planned pilot as designed** (temp 0 hardcoded, no draws/temperature flags, no matrix game, no probes, no stats). Fixable — the transport layer is small and clean.
- **Cloudflare:** a **complete, live-probed Cloudflare transport already exists** in `~/Documents/LLM_Search_Experiment` (TASK-1691/1693/1694, probed 2026-09): `_CloudflareRealTransport` in `harness/model_client.py` routes claude → `/ai/v1/messages`, gpt → `/ai/v1/responses`, gemini → `/ai/run`, with a 651-line test suite (`tests/test_cloudflare_transport.py`) and per-model routing in `harness/data/models.yaml`. **However** (i) the `CLOUDFLARE_API_TOKEN` in `~/.bashrc` currently **fails verification** ("Invalid API Token") and must be regenerated, and (ii) the live probes found **temperature and seed are hard-400 on the CF claude and gpt routes** — a direct conflict with the temperature-1 pilot design (see §5).

**Estimated pilot cost:** ~360 API calls, **≈$13–30**, worst case ~$60–80 if DeepSeek's chain-of-thought dominates all cells (unpriced risk: Sonnet's unreported CoT). **[I]**

---

## 2. What we accomplished (with artifacts)

| Artifact | Location | Content |
|---|---|---|
| 11–20 harness | `scripts/test_persona_conditions.py` (572 ln), `_31_40.py`, `_inverted.py` | 3 model endpoints in `_MODEL_ENDPOINTS` (:67-77), 5-section persona prompt (:159-188), temp 0.0 (:31), JSONL/CSV incremental save, schema at :89-100 |
| Die-roll harness | `scripts/test_die_roll.py` (653 ln) | 2 prompt variants, `true_roll`/`reported_number`/`lying_delta`/`prompt_hash` schema (:64-79) |
| Result data | `results/*_cond{2,3}_{11-20,31-40,inverted}.jsonl` (18 files), `{model}_die_roll*.jsonl` (6 files) | 20 records each, 2026-09-01/02, ~360 records total incl. Set B comparison |
| Pilot report | `~/Downloads/pilot_report_11_20_game.md/.html` | Model-dependence of the Reddit-persona effect; Sonnet **recognises the game and retrieves the human benchmark** (confound), DeepSeek reasons in character, GPT is degenerate-repetitive |
| Audit documents | `~/Downloads/six-game-llm-behavioural-transfer-audit-{v2,v4,updated}.html` | v2≡v4 byte-identical; `updated` restructures Table 2 and adds the 1–10 caveat (bonus changed 20→8, not a pure range shift) |
| Literature | `results/literature/` (10 papers: Abeler 2019, Capra 1999, Fudenberg-Liang 2019, …) | Converted reference set |

**Provenance:** six-game scripts entered in commit `f562016` (2026-09-02); repo HEAD `a76ea55` (2026-10-10) belongs to the unrelated twin2k thread. **[I] The six-game thread has been dormant since 2026-09-02.**

---

## 3. Outstanding feedback audit

| Item | Verdict | Evidence |
|---|---|---|
| **A. One coherent consistency definition** | **PARTIAL** — prose definition is coherent across audit versions ("transform preserving decision-relevant logic; succeeds when the same underlying reasoning is used") but has **no operationalisation**: no metric, no thresholds, no code. The Sonnet pilot (identical cond0/cond1 marginals from *different* personas) shows why marginals-only measurement misleads. | v4 text ~lines 121-124; `updated` lines 130/154/220/230; pilot report per-persona table |
| **B1. 1–10 variants + Manning & Horton human data** | **MISSING** — no "Manning"/"Horton" anywhere in HTMLs or repo. | grep across all audit texts |
| **B2. Their citation** | **MISSING** (1–10 attributed only to Arad & Rubinstein / Goeree-Louis-Zhang) | `updated` lines ~18-23 |
| **B3. Actual human distributions as targets** | **PARTIAL** — 17→32%, 18→30% (original) present; the required cycle figures (19→12%, 20→6%, 17→32%) and costless figures (19→40%, 20→15%, 17→9%) appear **nowhere**; v4 describes costless only qualitatively. | v4 Table 1 vs grep for the numbers |
| **B4. Cycle treatment effects** | **PARTIAL** — designed (v4 Table 2), zero data/scripts. | — |
| **B5. 1–10 human-tested vs pure range-shift distinguished** | **COMPLETE** in `updated` audit (explicit bonus-20→8 caveat; LLM test defined as clean 11–20→…→51–60 shift). | `updated` Table 1 |
| **C. Goeree & Holt 3×3 / matching-pennies** | **MISSING** — no script, no discussion; the 2×2-vs-3×3 discrepancy is nowhere acknowledged. Sixth game is specified as Fudenberg & Liang 3×3 only. | grep `matching.penn\|3x3\|3×3` |
| **D. Preregistration** | **MISSING** — zero hits for preregist/aspredicted/osf. | repo-wide grep |

---

## 4. Pipeline readiness

**Works:** persona loading (`personas/{username}.txt` ← `final_200_personas.csv`, 200 rows); crash-safe incremental JSONL+CSV with `raw_content`, `reasoning_content`, `prompt_hash`, `timestamp`; honest failure marking (`succeeded=False`); plain-urllib transport with clean 2-dict endpoint config.

**Blocks the pilot (all [F]):**

1. **Temperature hardcoded 0.0** (`test_persona_conditions.py:31`, `test_die_roll.py:44`); no `--temperature`/`--draws` CLI → **temp-1, 10-independent-draws design cannot run**. Existing temp-0 single-shots are not independent draws.
2. **Matrix game missing entirely** (only 2 of 3 pilot games exist; 2 of 6 total).
3. **Transformation rungs:** 1 of 5 implemented (31–40) plus inverted; die-roll ladder absent.
4. **Recognition probes:** no probe code for these games.
5. **Randomization/reproducibility weak:** persona order = CSV order; die roll unseeded `np.random.randint` (`test_die_roll.py:165`); no seed flags, no run manifest; only die-roll hashes prompts.
6. **JSON parsing fragile:** first-`{`-to-last-`}` blob extraction (`test_persona_conditions.py:222-240`); a structured-output/`response_format` capability exists in the sweep kit but is unused here.
7. **No statistics pipeline** for treatment effects / CIs vs human benchmarks for these games.
8. Minor: `run_multi_model.py` is orphaned (LM Studio targets); `test_persona_reasoning_openrouter_nos5.py` depends on an unfixed external `llm_traffic.jsonl` path.

**Call/cost estimate [I]:** minimal pilot = 3 games × 3 models × 2 persona conds × 10 draws = 180 decision calls; recognition probes 3 × 3 × 2 rungs × 10 = 180. Total ≈ **360 calls**, ≈1.8M completion + 0.9M prompt tokens → **$13–30** at pinned $2/$6 per M; up to ~$60–80 if DeepSeek CoT (measured 12.4k tok/call) generalizes.

---

## 5. Cloudflare AI Gateway migration

### What we already have (checked first, per your instruction)
- **A working, live-probed CF transport exists** in `~/Documents/LLM_Search_Experiment`: `harness/model_client.py` (`_CloudflareRealTransport`, lines ~580-911; routes dict at :73-77: `anthropic → ai/v1/messages`, `openai → ai/v1/responses`, `google → ai/run`), selected per-model via `provider: cloudflare` in `harness/data/models.yaml` (claude + gpt-5.6-luna + gemini all routed through CF; kimi/glm/qwen stay on OpenRouter). Tested in `tests/test_cloudflare_transport.py` (651 lines). Provenance: TASK-1691/1693/1694, live-probed 2026-09. **[F]**
- `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` in `~/.bashrc` (added 2026-09-15) — the same env vars the transport reads. **[F]**
- **Token is invalid right now:** live `POST /user/tokens/verify` → `{"success":false,"errors":[{"code":1000,"message":"Invalid API Token"}]}`. **[F]** Regenerate with **Account → Workers AI → Read** permission.

### ⚠️ Critical conflict with the pilot design [F, live-probed]
The existing transport's probes (TASK-1693, recorded in `models.yaml` + `model_client.py:519-546, 650-669`) found: **temperature and seed hard-400 on the CF claude (`/ai/v1/messages`) and gpt (`/ai/v1/responses`) routes** — they are deliberately OMITTED from those wire bodies (only gemini keeps temperature via `generationConfig`). The Cloudflare *docs* show temperature pass-through on the unified `/ai/v1/chat/completions` endpoint [F, RESULT-2665 §4], but our own live evidence says the provider-native routes reject it. Since the pilot's core methodology is **temperature-1 multi-draw**, this must be resolved empirically before any migration: one smoke call with `temperature: 1.0` on each candidate route (unified chat-completions, `/ai/v1/messages`, `/ai/v1/responses`). If temperature is rejected on all CF routes, the migration is **blocked for the experiment** (temp-1 sampling would silently become provider-default temperature — a fatal confound), and OpenRouter stays the pilot transport.

### Recommended architecture (revised after finding the existing transport) **[F/I]**
**Do not build anything new — reuse the LLM_Search_Experiment transport.** It already solves auth, routing, reasoning-off encoding (`reasoning: {"enabled": false}` — the only form the gateway accepts), max_tokens requirement (Anthropic-style bodies hard-require it; 32768 default at `model_client.py:78`), retry policy (4 attempts, exponential backoff, 4xx never retried), and full raw provenance (`cloudflare_raw` in response records). Two integration options **[I]**:
- **Option 1 (recommended): vendor the transport.** Port `_CloudflareRealTransport` (or import it cross-project) into the fos six-game scripts, keeping the per-family route map. Lowest risk; behaviour already pinned by 651 lines of tests.
- **Option 2: unified `/ai/v1/chat/completions`** (doc-quoted in RESULT-2665 §1) — a URL/auth-header swap in `_MODEL_ENDPOINTS`. Simpler, but unprobed for temperature and for luna chat-completions support.

**Doc-based architecture reference (either way, quoted from current docs):**
```
POST https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1/chat/completions
Authorization: Bearer {CLOUDFLARE_API_TOKEN}
{"model": "anthropic/claude-sonnet-5", "messages": [...], "temperature": 1.0}
```
Our model strings pass through **unchanged** (same `author/model` format as OpenRouter); the JSON body is unchanged; this is a URL + auth-header swap in the `_MODEL_ENDPOINTS` dicts (4 six-game files + optionally `openrouter_max_sweep*`). Provider keys via BYOK (stored under `default` alias; forwarded unchanged, no surcharge) or Unified Billing (5% credit fee, 200 req/60 s cap — irrelevant at 360 calls).

**Key operational facts:** caching is **off by default** (safe for independent draws; add `cf-aig-skip-cache: true` defensively; verify via `cf-aig-cache-status: MISS` in responses). **Keep gateway retries off** (`cf-aig-max-attempts` unset) so provider failures stay visible. Logs (incl. prompt/response) are **on by default** — consider `cf-aig-collect-log-payload: false` since we already persist raw responses ourselves. Anthropic `anthropic-version` pinning is only available on the provider-native route — on the unified route it depends on CF's upstream defaults.

**Two doc-level caveats (need a cheap smoke call each, by an implementer):** ① the `openai/gpt-5.6-luna` catalog page documents only the **Responses** format — chat-completions support through `/ai/v1/chat/completions` is undocumented; fallback is `/ai/v1/responses` (body-shape change confined to the transport function). ② `response_format`/JSON-mode survival through the gateway is undocumented per model.

**DeepSeek: keep direct** to `api.deepseek.com` — the gateway's unified catalog does not list `deepseek-v4-flash` via the DeepSeek provider (native passthrough exists, but our exact model string is not documented there), and direct already works.

**Migration plan (comparability-preserving):**
1. New CF token (Workers AI Read) + gateway creation; store Anthropic/OpenAI keys via BYOK.
2. Env additions: `CLOUDFLARE_ACCOUNT_ID` (exists), fresh `CLOUDFLARE_API_TOKEN`, optional `CF_AIG_GATEWAY_ID`. Keep `OPENROUTER_API_KEY` for rollback.
3. Smoke: 1 call/model; resolve the gpt-5.6-luna caveat above.
4. **Dual-route verification:** re-run a known temp-0 cell (e.g. 20 personas × cond2, Sonnet + luna) through both OpenRouter and the gateway; compare chosen-action distributions and finish_reason/error rates; proceed only if indistinguishable.
5. Flip `_MODEL_ENDPOINTS` for Claude/GPT; log `cf-aig-cache-status` into the JSONL; keep OpenRouter path intact as fallback.

---

## 6. Methodological risks

1. **Benchmark recognition confound [F from pilot report]:** Sonnet names the paradigm and retrieves the human distribution instead of reasoning in character — "success" on human replication can be benchmark leakage. The recognition probes (canonical + perturbed rung) are the designed control; they don't exist yet.
2. **Human targets:** without the exact cycle/costless distributions (§3 B3), "success" is undefined for the treatment cells; note success in the costless game must mean *upward* shift, not stability.
3. **2×2/3×3 category risk (C):** Goeree–Holt matching pennies is 2×2 — adopting it would silently break the "3×3 matrix game" category. Recommend either keeping Fudenberg–Liang 3×3 as the category benchmark, or explicitly renaming the category if Goeree–Holt is chosen.
4. **Sample sizes:** 20 personas × 10 draws = 200/cell is adequate for distribution comparison, but the pilot plan's "~10 draws per cell" over how many personas is undecided — at 10 draws × few personas, CIs on treatment effects will be wide. [I]
5. **Temperature-1 provider nondeterminism:** draws are only "independent" if caching/retries are off and calls are separate requests — handled in §5 but must be asserted in the data (cache-status per record).
6. **Consistency metric undefined (A):** without an operational metric, the transformation-sequence tests cannot pass/fail.

---

## 7. Prioritized restart plan

| # | Task | Depends on | Acceptance criterion |
|---|---|---|---|
| 1 | New CF API token + gateway; BYOK provider keys | — | `/user/tokens/verify` succeeds; gateway listed |
| 2 | Smoke calls (chat-completions for both models; JSON-mode) | 1 | Both models answer; luna format question resolved |
| 3 | Dual-route temp-0 comparability re-run | 2 | Sonnet+luna distributions indistinguishable OpenRouter vs gateway |
| 4 | Add `--temperature`, `--draws`, `--seed`, run manifest to six-game scripts; assert `cf-aig-cache-status=MISS` per record | — | Temp-1 ×10 draws reproducible from manifest |
| 5 | Harden JSON parsing (structured output or robust extractor) | — | 100% parse on 50-call dry sample |
| 6 | Write consistency-criterion doc: operational metric + thresholds (resolves A) | — | You + colleague sign off |
| 7 | Add cycle + costless variants with exact human distributions (12/6/32; 40/15/9) + Manning & Horton citation | 6 | Targets in code as data, cited |
| 8 | Decide matrix-game benchmark (Fudenberg–Liang 3×3 vs Goeree–Holt, resolving C) | — | Decision recorded |
| 9 | Implement recognition probes (canonical + 1 perturbed rung) | 4 | Probe records tagged separately in JSONL |
| 10 | Draft AsPredicted preregistration (design, hypotheses — prospective only, N, exclusions, analysis) | 6–9 | Registered before confirmatory run |
| 11 | Stats pipeline: treatment effects + CIs vs human effect sizes | 7 | Reproduces pilot-report tables from JSONL |
| 12 | Exploratory temp-1 pilot (~360 calls, $13–30) | 3,4,5,9 | ≥95% succeeded; data complete |

## 8. Decisions requiring your input

1. **Route decision given the temperature-1 requirement:** if CF rejects `temperature: 1.0` on every route shape (our own TASK-1693 probes say claude/gpt routes do), do we stay on OpenRouter for the pilot, or redesign? **This is now the gating question for the whole migration.**
2. **Matrix-game benchmark (C):** Fudenberg–Liang 3×3 (keeps category) vs Goeree–Holt (renames category to 2×2 mixing matrix)? My read: keep 3×3, treat Goeree–Holt as a separate candidate replication.
2. **Personas per cell in the pilot:** 20 personas × 10 draws (~$13–30) vs fewer personas for cost?
3. **Migration scope:** migrate the `openrouter_max_sweep*` survey scripts too, or only the six-game thread?
4. **Gateway logging:** keep default full-payload logging (debuggability) vs `cf-aig-collect-log-payload: false` (privacy, we already store raws)?
5. Confirm the cycle/costless human figures' source (they're not in the repo — presumably from the Manning & Horton paper you cited) so they can be transcribed with a citation.
6. Reuse LLM_Search_Experiment's `models.yaml` slug decisions (dated canonical ids like `openai/gpt-5.6-luna-20260709`, `anthropic/claude-sonnet-5-20260630`) in the six-game pilot for version pinning?

---

## Five most important next actions

1. **Regenerate the Cloudflare API token** (current one is dead) and run the **temperature-1 smoke test on all three CF route shapes** — this single test decides whether the migration is compatible with the pilot at all.
2. **Smoke-test + dual-route comparability re-run** (§5 step 3–4) before any pilot traffic moves.
3. **Add temp-1 / draws / seed CLI + manifest** to the six-game scripts — the single hardest pilot blocker.
4. **Operationalise the consistency criterion** and get colleague sign-off (feedback A; everything in the transformation tests hangs on it).
5. **Draft and register the AsPredicted preregistration**, separating the already-observed exploratory results (temp-0 pilot, Sonnet recognition confound) from genuinely prospective predictions.

*No implementation performed — awaiting your approval.*

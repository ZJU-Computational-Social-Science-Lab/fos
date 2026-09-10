# R1LP — the logprob experiment (design)

R1LP is the second version of the five-model experiment. Where `R1-5MODEL`
samples N grammar-constrained draws per prompt, R1LP reads the **model's own
probability** of "purchase" versus "not purchase" from **logprobs**, with
**no grammar**, and makes **one scoring pass per prompt**. It is built to
launch the day after the sampling run finishes; building it does not start
any run, load any model, or contact any server.

## Same design as R1-5MODEL

Everything except the scoring mechanism is identical to the 5-model queue:

- **5 models, one invocation**: `openai/gpt-oss-20b`, `google/gemma-4-26b-a4b`,
  `qwen/qwen3.8-27b`, `nvidia/nemotron-cascade-2-30b-a3b`,
  `meta/muse-glimmer`.
- **40 products**, **11 price levels** (0–200% of regular price), **bare**
  (`none`) legs and **demographics** legs, **blinded** and **unblinded**.
- **Personas**: model *i* answers pool personas `[20i, 20i+20)` of every
  product's shared 100-persona pool (20 personas per model).
- **One run directory**, per-model leg subdirs
  `<run>/<safe_model>/<depth>_<blinding>/`, cell-granular durability
  (`records.jsonl` is the resume state), `--resume`, `progress.json`,
  `results.csv`, and a 20-leg manifest merged exactly once.

The only differences:

- `grammar = None` on every call (no constrained decoding).
- **One scoring pass per prompt** instead of N draws (one cell = one
  prompt). Per model: bare `40 × 11 × 2 = 880` + personas
  `20 × 40 × 11 × 2 = 17,600` = **18,480**; the five models = **92,400**.

## The two mechanisms (`--logprob-mode`)

### `first_token` (default; 1 call/prompt)

`POST /v1/chat/completions` with `max_tokens=1`, `temperature=1.0`,
`logprobs=true`, `top_logprobs=20`. At the decision position the returned
top-logprobs are split by branch:

- `p_buy` = Σ `exp(logprob)` over tokens whose text continues the
  **purchase** branch (leading punctuation/whitespace stripped, then
  case-insensitive prefix `purchase`);
- `p_nobuy` = Σ over tokens starting the **not** branch;
- `branch_mass = p_buy + p_nobuy`;
- a flag (`neither_branch_in_top_k`) is recorded when neither branch appears
  in the top-k, so the cell is visible instead of silently read as 0.

The raw top-k list, `branch_mass` and the flag are stored on the record.

### `candidate_scoring` (2 calls/prompt, teacher-forced)

`POST /completions` with the chat-templated prompt **plus the candidate
appended**, `n_predict=0`, `logprobs=true`, `n_probs=20`, `temperature=1.0`.
Each of the two candidates (`purchase`, `not purchase`) is scored in its own
call. The candidate's own trailing token logprobs are summed:

- `lp_sum`, `lp_tokens`, `lp_mean = lp_sum / lp_tokens` per candidate;
- `p_buy = softmax([lp_buy_sum, lp_nobuy_sum])` (and a length-normalized
  variant `p_buy_normalized` from `[lp_buy_mean, lp_nobuy_mean]`).

The parser tolerates llama-server's response variants
(`completion_probabilities`, `prompt_logprobs`, per-token `top_logprobs`
and per-token `probs`) and always keeps a truncated (≤ 2 KB) raw response
for audit.

## Record schema

Every existing field of a sweep record plus:

| field | meaning |
| --- | --- |
| `logprob_mode` | `first_token` or `candidate_scoring` |
| `p_buy_logprob` | model p(buy) from the score |
| `p_nobuy_logprob` | model p(not buy) from the score |
| `branch_mass` | `p_buy + p_nobuy` (first_token); 1.0 for a two-way softmax |
| `top_logprobs` | the raw top-k list `[{token, logprob}]` |
| `lp_buy_sum` / `lp_nobuy_sum` | candidate log-score sums |
| `lp_buy_tokens` / `lp_nobuy_tokens` | candidate token counts |
| `raw_logprob_response` | truncated raw response for audit (≤ 2 KB) |
| `neither_branch_in_top_k` | first_token: no branch in the top-k |

`parsed_purchase` stays `null` in logprob mode and `succeeded` means **the
scoring call succeeded** (not whether a text answer parsed).

## Cost model

| leg | cells per model | HTTP calls (`first_token`) | HTTP calls (`candidate_scoring`) |
| --- | --- | --- | --- |
| bare (2 blindings × 40 × 11) | 880 | 880 | 1,760 |
| demographics (2 × 40 × 20 × 11) | 17,600 | 17,600 | 35,200 |
| **per model** | **18,480** | **18,480** | **36,960** |
| **5 models** | **92,400** | **92,400** | **184,800** |

`--dry-run` prints the 18,480-per-model / 92,400-total prompt counts. The
candidate mechanism doubles the HTTP calls (two teacher-forced probes per
prompt); `first_token` is the default and the cheaper one.

## Analysis

`scripts/r1_logprob_analysis.py` reads a logprob run directory and produces
a table directly comparable to the sampling run's interim report:

- per-cell `p(buy)` = mean of `p_buy_logprob` over the cell's personas (or
  plain draws);
- cell **MAE** against the human benchmark
  (`/home/justin/work/research/TASK-1496/pbuy_product_level.csv`);
- mean **per-product shape correlation** (Pearson *r* across price levels);
- each metric twice: **0% (free) level excluded** as the primary number,
  with-free as the robustness number (the sampling report's convention).

```
python3 scripts/r1_logprob_analysis.py results/unblinding/R1LP-<stamp> \
    --out results/unblinding/R1LP-<stamp>/logprob_analysis.csv
```

## Open item — probe before the run (first step tomorrow)

The exact response shape of llama-server's `/completions` is **not**
validated yet: the `n_predict=0` teacher-forced path may return
`completion_probabilities`, `prompt_logprobs`, per-token `top_logprobs`, or
something else, and the trailing-token count of each candidate depends on
the model's tokenizer. The local ChatML rendering in
`render_chat_template` is also a documented fallback, not a per-model
template.

**Before the real run, and before any long queue, make a 2–4 call probe**
against each served model (server already loaded by the operator):

1. one `first_token` call and confirm the top-logprobs shape and that the
   `purchase`/`not` tokens appear;
2. one `candidate_scoring` call and confirm which per-token field the
   server returns and that the last 1–2 tokens are exactly the candidate;
3. if the shape differs from the parser's expectations, extend
   `parse_candidate_response` / `count_candidate_tokens` and re-run the
   offline tests.

The probe is the first step of the R1LP launch session and uses ≤ 4 calls
per model; it starts no run and touches no paused run directory.

## Launch command for tomorrow

From the main checkout, where the archived pools live:

```
python3 scripts/launch_grid.py --profile R1LP --logprob-mode first_token
```

- default run dir `results/unblinding/R1LP-<timestamp>/`;
- add `--run-name <name>` for a fixed name;
- resume after any stop/crash with the same command plus
  `--run-name <name> --resume` (completed (model, leg) pairs and durable
  cells are skipped; one cell = one prompt);
- switch to `--logprob-mode candidate_scoring` for the teacher-forced
  variant (double the HTTP calls);
- `--dry-run` prints the 18,480/model and 92,400-total plan, offline;
- `--smoke` is refused for the 5-model queues (smoke models individually
  with `--profile R1` first).

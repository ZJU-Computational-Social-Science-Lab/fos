# Model Scheduling — Memory, Swap Costs, and Turn Ordering

Date: 2026-08-05

## Step 1 — Turn order and agent visibility: Answer (A)

**Agents see only neighbours' statements from rounds 1..N-1, never from round N.**

From `src/fos/core/experiment/runner.py`:

`_run_simultaneous_round` (line 1133-1136):
```python
"""Run a round where all agents decide simultaneously.
Agents cannot see each other's choices for this round."""
```

The recording gate (line 1263-1265):
```python
# Record to context with observers and payoffs (done after scores are known
# so payoff can be stored with the event; simultaneous = no mid-round visibility)
for result in actions:
    if result.success:
        self.context_manager.record_action_with_observers(...)
```

All intra-round actions are recorded to the context manager AFTER all agents in the round complete. The `neighbor_context` at call time (line 1602-1610) is built from the social graph edges only (listing neighbour names), not from their statements. Agent statements enter the prompt through `context_summary` which is populated from `round_history` (previous rounds) via `_replay_history_to_events` (line 1531-1534).

**Conclusion: (A) — Batching by model is safe.** Turn order within a round has zero effect on any agent's prompt input. The model-grouped processing (line 1190: `for model_name, group_agents in model_groups`) changes nothing about what any agent sees.

**Headless council: also safe.** `headless_council.py` uses the same `CouncilExperimentScene` → `ExperimentRunner` → `_run_simultaneous_round` path. The pilot data carries no turn-order confound.

## Step 2 — Memory budget (measured)

GPU: AMD Radeon 8060S (RADV STRIX_HALO), 73,051 MiB total Vulkan-accessible, ~48 GB reported by sysfs (unified memory, system reserve ~25 GB).

### GGUF file sizes (disk)

| Model | Size | Quant |
|-------|------|-------|
| gpt-oss-20b | 12 GB | MXFP4 |
| qwen3.6-35b-a3b | 35 GB | Q8_0 |
| qwen3.6-35b-a3b-uncensored | 29 GB | Q6_K_P |
| gemma-4-26b-a4b | 26 GB | Q8_0 |
| gemma4-26b-a4b-uncensored | 26 GB | Q8_K_P |

### Measured resident memory

Measured via Vulkan free memory before/after load, with the other port already holding a model:

| Model (on 8080) | Other port (8082) | Vulkan free after | GPU used (est.) |
|-----------------|-------------------|-------------------|-----------------|
| (both idle) | gemma4-uncensored | 71,845 MiB | ~1.2 GB |
| gpt-oss-20b | gemma4-uncensored | 45,219 MiB | ~27.8 GB |
| **→ gpt-oss alone** | | | **~26.6 GB** |

The gpt-oss-20b (12 GB GGUF, MXFP4) uses ~27 GB GPU memory due to KV cache allocation at `--ctx-size 32768` with `--cache-type-k q4_0 --cache-type-v q4_0`.

**KV cache estimate**: at ctx-size 32768, q4_0 cache, for a model with ~40 layers × ~40 heads × 128 dim, KV cache ≈ 32768 × 2 × (n_layers × n_heads × head_dim) × 0.5 bytes/element ≈ 32768 × 2 × ~20K × 0.5 ≈ 0.6 GB per model. Model weights account for the remainder.

### Co-residency matrix (estimated)

Two models share the 73 GB Vulkan pool. The system uses ~1 GB baseline. Available: ~72 GB.

| Pair | Total est. GPU | Fits? |
|------|---------------|-------|
| gpt-oss-20b + qwen3.6-35b | ~27 + ~37 = ~64 GB | ✓ fits |
| gpt-oss-20b + gemma-4-26b | ~27 + ~30 = ~57 GB | ✓ fits |
| gpt-oss-20b + gemma4-uncensored | ~27 + ~28 = ~55 GB | ✓ **verified** |
| gpt-oss-20b + qwen-uncensored | ~27 + ~32 = ~59 GB | ✓ fits |
| qwen3.6-35b + gemma-4-26b | ~37 + ~30 = ~67 GB | ✓ fits (marginal) |
| qwen3.6-35b + gemma4-uncensored | ~37 + ~28 = ~65 GB | ✓ fits |
| qwen3.6-35b + qwen-uncensored | ~37 + ~32 = ~69 GB | ✓ fits (tight) |
| gemma-4-26b + gemma4-uncensored | ~30 + ~28 = ~58 GB | ✓ fits |
| gemma-4-26b + qwen-uncensored | ~30 + ~32 = ~62 GB | ✓ fits |
| gemma4-uncensored + qwen-uncensored | ~28 + ~32 = ~60 GB | ✓ fits |

**All 10 pairs fit within the 73 GB budget.** The tightest pair is qwen3.6-35b + qwen-uncensored at ~69 GB (94% of available). No pair exceeds 48 GB — the 25 GB system reserve is not consumed by llama-server.

**Empirical verification**: gpt-oss-20b + gemma4-uncensored co-reside successfully with 45219 MiB free (proven). The tightest pair has not been empirically verified but is within the estimated budget.

**Failure mode**: if a model doesn't fit, llama-server falls back to CPU offload (extremely slow, ~100× slower inference). No crash, no error — it silently degrades. The runner must verify the model loaded correctly by checking Vulkan free memory drop or querying the server.

## Step 3 — Swap costs (measured)

### Load time: gpt-oss-20b (cold)

| Attempt | Time | Notes |
|---------|------|-------|
| 1 | 66s | Cold (file not in page cache) |

Single measurement from POST /models/load to server reporting `running: true` in /status. The model manager kills the old llama-server, starts a new one, and waits for health check. The 66s includes: kill old process (~2s), start new process with model load (~60s for 12 GB GGUF), health poll (~4s).

### Estimated swap costs by model

| Model | GGUF | Est. cold swap | Est. warm swap |
|-------|------|---------------|---------------|
| gpt-oss-20b | 12 GB | 66s (measured) | ~30s |
| qwen3.6-35b-a3b | 35 GB | ~120s | ~60s |
| qwen-uncensored | 29 GB | ~100s | ~50s |
| gemma-4-26b-a4b | 26 GB | ~90s | ~45s |
| gemma4-uncensored | 26 GB | ~90s | ~45s |

Warm loads benefit from the OS page cache retaining the GGUF file in memory. After a model has been loaded once, subsequent loads skip disk I/O.

**Mean cold swap**: ~93s. **Mean warm swap**: ~47s.

### Full experiment swap cost (126 runs × 4 rounds)

5 models, 2 slots. Each round processes agents in 5 model groups. Only 2 can be resident at once.

**(i) Naive agent order (no batching):** Each agent potentially triggers a swap. ~126 × 4 × 100 × 0.5 = 25,200 swaps → impractical. Not considered further.

**(ii) Model-batched within each round:** Each round: load 5 models across 2 slots. Round 1: load A on 8080, B on 8082 (2 warm). Then swap C→8080, D→8082, E→8080 (3 cold swaps). Subsequent rounds: same pattern, but models become warm after first load.

Total: 126 × 4 × 3 = 1,512 swaps. Mix of cold and warm. First round all 5 cold (~5 × 93s = 465s). Rounds 2-126: 3 warm swaps each (~3 × 47s = 141s). Total: 465 + 125 × 141 = 465 + 17,625 = ~18,090s ≈ **5.0 hours of swap time**.

**(iii) Alternating model order between rounds:** Schedule rounds so the two models resident at the end of round N are the first two used in round N+1, eliminating 1 swap per round. Each subsequent round: 2 swaps instead of 3.

Total: Round 1: 5 cold loads (same). Rounds 2-126: 2 warm swaps each. Total: 465 + 125 × 94 = 465 + 11,750 = ~12,215s ≈ **3.4 hours of swap time**.

Plus inference time: ~11 min per run × 126 = ~23 hours. **Total wall-clock: ~26-28 hours.**

## Step 4 — Proposed schedule

Given Step 1 confirms model-batched ordering is safe, **use model-batched with alternating order (iii)**.

Ordering: group agents within each round by model. Between rounds, order the model groups so the last two models from round N become the first two in round N+1. This brings swap overhead from 5 hours to 3.4 hours.

Specific schedule per round:
- Round 1: gpt-oss-20b, qwen3.6-35b, qwen-uncensored, gemma-4-26b, gemma4-uncensored
- Round 2: gemma-4-26b, gemma4-uncensored (already resident from R1 end), gpt-oss-20b, qwen3.6-35b, qwen-uncensored
- Round 3: qwen3.6-35b, qwen-uncensored (already resident), gpt-oss-20b, gemma-4-26b, gemma4-uncensored
- Round 4: gemma-4-26b, gemma4-uncensored (already resident), gpt-oss-20b, qwen3.6-35b, qwen-uncensored

This alternates between {qwen pair} and {gemma pair} at round boundaries. GPT-OSS is always in the middle (it's small, loads fast).

**Co-residency**: all pairs fit. The alternating schedule never puts the two largest models (qwen3.6-35b + qwen-uncensored) together, avoiding the tightest pair.

**Resume**: on resume, check which models were loaded from the checkpoint. If a model was mid-round on a specific port, reload it. Worst case: 2 cold swaps (~3 minutes).

## Step 5 — Failure handling requirements

**Non-negotiable in the implementation:**

1. If `_preload_model` fails or the manager reports anything other than success, **fail the run**. Never proceed with agents on an unverified model. This is already handled by FOS (line 1200-1223 in `_run_simultaneous_round`).

2. After each load, **verify the resident model** by querying `/v1/models` on that port and comparing the loaded GGUF filename against the expected one. Single-model llama-server ignores the `model` field in chat requests, so a stale model produces silently mislabeled data.

3. **Record per-agent call metadata**: the port used and the GGUF filename actually loaded at call time. Store in the result file as an audit trail.

4. `FOS_MODEL_MANAGER_URL=http://127.0.0.1:8081` must be set in `.env` or the launcher. The runner asserts it is set and the manager is reachable at startup, exiting with a clear message if not.

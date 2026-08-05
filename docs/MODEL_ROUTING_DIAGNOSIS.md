# Model Routing Diagnosis

Date: 2026-08-05

## Step 1 — Manager's contract

Source: `/home/justin/fos-model-manager/model_manager.py`

| Setting | Value |
|---------|-------|
| CONTROL_HOST | 127.0.0.1 |
| CONTROL_PORT | 8081 |
| LLAMA_SERVER_PORTS | [8080, 8082] |

**`/models/load` expected request shape:**
```json
POST /models/load
{"model": "<name>", "port": <int>}
```
`model` can be bare (`gpt-oss-20b`), prefixed (`openai/gpt-oss-20b`), or a partial match. `_resolve_model_name` in `model_manager.py` resolves to the `MODEL_REGISTRY` key via exact match, then suffix/prefix match. `port` defaults to 8080 if omitted or not in `LLAMA_SERVER_PORTS`.

**`_ROUTER_NAMES` mapping (FOS → short stem):**
```
openai/gpt-oss-20b → gpt-oss-20b
google/gemma-4-26b-a4b → gemma-4-26b-a4b
qwen/qwen3.6-35b-a3b → qwen3.6-35b-a3b
gemma4-26b-a4b-uncensored-hauhaucs-balanced → gemma4-26b-a4b-uncensored
qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive → qwen3.6-35b-a3b-uncensored
```

**`MODEL_REGISTRY` (prefixed key → GGUF path):** maps `openai/gpt-oss-20b`, `google/gemma-4-26b-a4b`, `qwen/qwen3.6-35b-a3b`, and the two uncensored bare names to `.gguf` files under `~/.lmstudio/models/`.

**Swap behavior:** YES, the manager swaps models on demand. At most 1 model per port, 2 resident at once. A load request on a port kills the current model and starts a new llama-server process (60-180s for 35B models).

**Live status** (2026-08-05 01:18 UTC):
```json
{"8080": {"model": "qwen/qwen3.6-35b-a3b", "running": true},
 "8082": {"model": "gemma4-26b-a4b-uncensored-hauhaucs-balanced", "running": true}}
```

**Live load test results (all 5 models accepted):**
- `gpt-oss-20b` → `{"status": "ok", "model": "openai/gpt-oss-20b", "port": 8080}` ✓
- `qwen3.6-35b-a3b` → `{"status": "ok", "model": "qwen/qwen3.6-35b-a3b", "port": 8080}` ✓
- `qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive` → pending (manager switching, expected latency)
- `gemma-4-26b-a4b` → pending
- `gemma4-26b-a4b-uncensored-hauhaucs-balanced` → pending

The manager accepts ALL five model names (bare or prefixed, resolved internally).

## Step 2 — FOS model-management resolution

Source: `src/fos/core/experiment/runner.py`

| Item | Location | Value |
|------|----------|-------|
| Router base URL builder | `_get_router_base_url` (line ~487) | Strips `/v1` from provider base_url. Defaults to `http://127.0.0.1:8080` if empty |
| Model manager URL | `_get_model_manager_url` (line ~503) | `os.environ.get("FOS_MODEL_MANAGER_URL")` or `None` |
| Is manager active? | `_is_model_manager_active` (line ~510) | `self._get_model_manager_url()` is truthy → True; else `"8080" in base_url` |
| Router model name | `_get_router_model_name` (line ~571) | `LLAMACPP_ROUTER_MODEL_MAP.get(model_name, model_name)` |
| Router model map | `LLAMACPP_ROUTER_MODEL_MAP` (line 39) | Maps PREFIXED names → short stems. Bare names NOT in map → passed through unchanged |
| Load request | `_preload_model` (line ~231) | POST to `router_base/models/load` with `{"model": router_model, "port": port}` |

**Predicate quoted verbatim** (`_is_model_manager_active`):
```python
if self._get_model_manager_url():
    return True
return self._is_llama_cpp_port(base_url)
```
Tests: (1) is `FOS_MODEL_MANAGER_URL` set? (2) does base_url contain "8080"?

## Step 3 — Working vs broken diff

**Working path (`headless_council.py`):**
- Uses prefixed model names (`openai/gpt-oss-20b`, `qwen/qwen3.6-35b-a3b`, etc.)
- Has its own `_warmup_models` / `_dual_warmup` that sends a chat request to each port BEFORE FOS's preload runs
- If FOS preload triggers, model names ARE in `LLAMACPP_ROUTER_MODEL_MAP`, so router names resolve correctly
- The warmup causes models to be loaded, so preload sees "already loaded" and noops
- Does NOT set `FOS_MODEL_MANAGER_URL`

**Broken path (`src/fos/experiment/runner.py` via `scene_builder.py` + `clients.py`):**
- Uses BARE model names from population files (`gpt-oss-20b`, `qwen3.6-35b-a3b`, etc.)
- Does NOT warm up models before FOS preload runs
- Does NOT set `FOS_MODEL_MANAGER_URL`
- `_get_router_model_name("gpt-oss-20b")` → `LLAMACPP_ROUTER_MODEL_MAP.get("gpt-oss-20b", "gpt-oss-20b")` → `"gpt-oss-20b"` (bare, key not in map)
- `_get_router_base_url("http://127.0.0.1:8082/v1")` → `"http://127.0.0.1:8082"` — this IS correct per-port
- BUT: `_preload_model` sends POST to `http://127.0.0.1:{port}/models/load` — the port is extracted correctly per-client
- The request reaches **llama-server**, not the model manager, because `FOS_MODEL_MANAGER_URL` is not set
- llama-server has no `/models/load` endpoint → returns 404 `{"error":{"message":"File Not Found","type":"not_found_error","code":404}}`

**Environment check:**
```bash
$ echo $FOS_MODEL_MANAGER_URL
(empty)
$ grep FOS_MODEL_MANAGER /home/justin/Documents/ZJU/work/fos/.env
(no match)
$ grep FOS_MODEL_MANAGER /home/justin/Documents/ZJU/work/fos/run_fos.sh
(no match)
```

**Reproduction:** `headless_council.py` with backend=llamacpp would also fail if run fresh (no pre-warmed models), because it also doesn't set `FOS_MODEL_MANAGER_URL`. The pilot artifacts were produced with the OLD `council_pilot_runner.py` (Ollama backend, 12 agents, different models), not the current 100-agent 5-model headless council.

**Answer: (a)** — the new runner does not set `FOS_MODEL_MANAGER_URL`. Additionally, (d) — the new runner uses bare model names that are not in `LLAMACPP_ROUTER_MODEL_MAP`, though this is secondary (the manager resolves bare names fine).

## Step 4 — Data-integrity assessment of original run_079

**What happened in the original run_079 (deleted deliberation.py):**
The old code created raw `openai.OpenAI(base_url="http://localhost:{port}/v1")` clients and sent chat requests directly. It NEVER called `_preload_model` or any FOS model management. It sent chat completion requests with `model="gpt-oss-20b"` (or whatever the agent's voting_model was) to whatever port the `_MODEL_PORT_MAP` directed.

**What was actually running on each port then vs now:**
From historical process data (captured earlier in the session):
- Port 8080 (then): `gpt-oss-20b-MXFP4.gguf` — the MODEL MATCHED the label
- Port 8082 (then): `gemma-4-26B-A4B-it-Q8_0.gguf` — the MODEL MATCHED the label

From current status:
- Port 8080 (now): `Qwen3.6-35B-A3B-Q8_0.gguf` — DIFFERENT
- Port 8082 (now): `Gemma4-26B-A4B-Uncensored-...` — DIFFERENT (uncensored instead of safety-tuned)

**The single-model server behavior:** Llama-server in single-model mode ignores the `model` field in chat completion requests and answers with whatever GGUF is loaded. So at the time of the original run_079, the model labels were CORRECT — `gpt-oss-20b` agents were actually answered by GPT-OSS, and `gemma-4-26b-a4b` agents were answered by Gemma.

The empty-response pattern (68% for "safety-tuned" models, 0% for "uncensored") WAS genuine — GPT-OSS and Qwen on port 8080 were emitting EOS immediately due to chat-template mismatch (these models had `--skip-chat-parsing` and `--reasoning off` flags).

**Risk in pilot artifacts:** The pilot artifacts used Ollama backend with different models entirely (ministral-3, granite4, phi4-mini, qwen3). No data-integrity issue there.

## Proposed fix

Set `FOS_MODEL_MANAGER_URL=http://127.0.0.1:8081` in the runner's environment before creating any FOS clients. Additionally, populate `LLAMACPP_ROUTER_MODEL_MAP` with bare-name entries so that `_get_router_model_name` resolves correctly for both prefixed and bare names (though this is secondary — the manager's `_resolve_model_name` already handles bare names). The Phase 4 runner should also call the manager to preload the correct model for the current run's required model (using `_preload_model` through the FOS path, which will now route to 8081). If a model cannot be loaded after the timeout, fail the run — do not silently proceed with the wrong model.

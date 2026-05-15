# fos.core.agent Import Investigation

## The problem

`from fos.core.agent import Agent` fails with `ModuleNotFoundError` in all contexts:
- `python -c "from fos.core.agent import Agent"` — FAILS
- `PYTHONPATH="src" python -c "from fos.core.agent import Agent"` — FAILS
- Direct `import fos.backend.services.simtree_runtime` — FAILS (cascading from line 8)

**The user's initial hypothesis ("it resolves inside pytest") is incorrect.** The module has never resolved anywhere. No test exercises the code paths that import `fos.core.agent` — all passing tests use `ExperimentAgent` from `fos.core.experiment.agent`, not the legacy `Agent`. The import is a latent bug that only triggers when the backend server starts or when `simtree_runtime`/`scenes.py`/`policy_cascade` modules are loaded.

## Files importing from fos.core.agent

| # | File | Line | Usage |
|---|------|------|-------|
| 1 | `src/fos/core/scenes/policy_cascade/base.py` | 6 | Type annotation (`Agent \| None`), method calls (`agent.properties`, `agent.language`) |
| 2 | `src/fos/core/scenes/policy_cascade/distortion.py` | 7 | Type annotation (`agent: Agent`) |
| 3 | `src/fos/core/scenes/policy_cascade/followup.py` | 5 | Type annotation (`agent: Agent`), method calls |
| 4 | `src/fos/core/scenes/policy_cascade/prompts.py` | 3 | Type annotation (`agent: Agent`) |
| 5 | `src/fos/core/scenes/policy_cascade/messages.py` | 5 | Type annotation (`agent: Agent`) |
| 6 | `src/fos/core/scenes/policy_cascade/threads.py` | 6 | Type annotation (`agent: Agent`) |
| 7 | `src/fos/core/scenes/policy_cascade/runtime.py` | 14 | Type annotation (`agent: Agent`), method calls |
| 8 | `src/fos/backend/api/routes/scenes.py` | 9 | `Agent.deserialize({...})` — constructs a dummy agent for scene preview |
| 9 | `src/fos/backend/services/simtree_runtime.py` | 8 | `Agent.deserialize({...})` — constructs agents for Simulator (lines 203, 636) |

## Why pytest works but python -c does not

**It doesn't.** The import fails in pytest too. The reason all tests pass is that no test exercises the `policy_cascade`, `simtree_runtime`, or `scenes.py` import paths. All 20+ passing tests use `ExperimentAgent` from `fos.core.experiment.agent`, which exists and works fine. The `fos.core.agent` import is dead code from the user's perspective — it only breaks at runtime when the backend server tries to load these modules.

Conftest files (`tests/smoke_tests/conftest.py`, `tests/core/conftest.py`) do not add anything to `sys.modules` or `sys.path` that would resolve `fos.core.agent`.

## What Agent is actually used for

### policy_cascade (7 files)
All uses in `policy_cascade/` are **type annotations** (`agent: Agent`) and attribute access (`agent.properties`, `agent.language`, `agent.role_prompt`, `agent.user_profile`). The `Agent` type is used as a duck-typed interface — the code accesses `.properties` (dict), `.language` (str), `.role_prompt` (str), `.user_profile` (str), `.consecutive_llm_errors` (int), `.is_offline` (bool), `.short_memory.history` (list). This is the legacy `Agent` class from socialsim4 which had all these attributes.

### simtree_runtime.py (2 actual construction sites)
- **Line 203** (`_build_tree_for_scene`): `Agent.deserialize({...})` creates a minimal placeholder agent for preview.
- **Line 636** (`_build_tree_for_sim`): `Agent.deserialize(agent_data)` constructs real agents from config, then mutates them with `.name`, `.user_profile`, `.role_prompt`, `.properties`, `.action_space`, `.language`, `.knowledge_base`, `.documents`, `.history`, `.memory`, `.score`, `.set_global_knowledge()`.

### scenes.py (1 construction site)
- **Line 124** (`scene_config_template`): `Agent.deserialize({...})` creates a dummy agent to introspect available scene actions via `scene.get_scene_actions(dummy)`.

## Root cause

The `fos.core.agent` module was never created during the socialsim4 → fos migration. The legacy `Agent` class (with `deserialize()`, `system_prompt()`, `short_memory`, etc.) was part of Pipeline B in socialsim4 and was not migrated, but 9 files still import it.

## Proposed fix

**Option A (minimal):** Create `src/fos/core/agent.py` as a re-export shim that re-exports the legacy Agent from wherever it survives, or provides a compatible stub.

**Option B (correct):** The legacy `Agent` class is used in two distinct ways:
1. **policy_cascade**: Only needs a duck-typed agent with `.properties`, `.language`, `.role_prompt`, `.user_profile`. A `Protocol` could replace the type annotation.
2. **simtree_runtime + scenes.py**: Needs `Agent.deserialize()` to construct full agents with `short_memory`, `action_space`, `set_global_knowledge()`, etc. This is the legacy Simulator pipeline.

Since `ExperimentAgent` lacks `.deserialize()`, `.short_memory`, `.action_space`, `.set_global_knowledge()`, the backend files (`simtree_runtime.py`, `scenes.py`) cannot simply swap to `ExperimentAgent`. A minimal `Agent` class (or reconstituted from socialsim4) is needed for the legacy Simulator pipeline that non-experiment scenes still use.

**Recommended:** Create `src/fos/core/agent.py` with a minimal `Agent` class that supports `deserialize()` and the attributes accessed by `simtree_runtime.py` and `policy_cascade/`. The socialsim4 `Agent` class should be used as reference.

## Risk

- **policy_cascade/** files: The 7 files only use `Agent` as type annotations and attribute access. Any object with the right attributes works (duck typing). Risk is low — a Protocol or the same Agent class works.
- **simtree_runtime.py**: Lines 203 and 636 call `Agent.deserialize()` and then heavily mutate the agent. The deserialized agent must be compatible with `Simulator` (which expects the legacy Agent interface). This is the highest-risk area.
- **scenes.py**: Line 124 uses `Agent.deserialize()` only for action introspection. Low risk — just needs `.properties` to be a dict.
- If the fix provides an incomplete `Agent` class, runtime errors will appear when `Simulator` tries to call `.system_prompt()`, `.short_memory`, or `.set_global_knowledge()` on the agent.

## Follow-up: scenes router import chain (2026-05-15)

### Blocking module: `fos.core.tools.web.search`

The entire route router (`fos.backend.api.routes`) fails to load because `routes/__init__.py` eagerly imports all submodules. The `simulations` subpackage fails first, blocking everything (including `scenes`).

**Full chain:**
```
fos.backend.api.routes.__init__
  → fos.backend.api.routes.simulations.__init__ (create_router)
    → .helpers (line 29)
      → fos.core.tools.web.search  ← ModuleNotFoundError: No module named 'fos.core.tools'
```

### What `fos.core.tools.web.search` is used for

| # | File | Line | Usage |
|---|------|------|-------|
| 1 | `src/fos/backend/api/routes/simulations/helpers.py` | 29, 105 | `create_search_client(s_cfg)` — passed as `"search"` client in agent client map |
| 2 | `src/fos/backend/services/experiment_tasks.py` | 20, 161 | `create_search_client(s_cfg)` — passed as `"search"` client for experiment worker |
| 3 | `src/fos/backend/api/routes/simulations.py.deprecated` | 22 | Dead file (old socialsim4 import) |

Both active call sites:
1. Receive a `SearchConfig` (from `fos.core.search_config` — this module **exists**)
2. Call `create_search_client(s_cfg)` to get a search client
3. Include it as `"search": search_client` in a `clients` dict passed to the Simulator/agents

### Status of `src/fos/core/tools/`

**The directory does not exist.** No `tools/` directory, no `tools/web/`, no files. Git history also shows no commits for `**/tools/web/**`. This module was never migrated from socialsim4.

### Missing modules blocking the router (complete list)

1. **`fos.core.tools.web.search`** (intentionally left behind — web search tools not migrated from socialsim4)
   - Needs at minimum: `create_search_client(config: SearchConfig) -> SomeClient`
   - The `SearchConfig` dataclass exists at `fos.core.search_config` with fields: `dialect`, `api_key`, `base_url`, `params`
   - A minimal stub returning `None` or a no-op client would unblock the import chain

Note: `fos.core.agent` (documented above) also blocks `scenes.py` directly (line 9), but that is a separate missing module. The `tools.web.search` issue blocks the `simulations` route package and therefore the entire route router.

# Migration: socialsim4 → fos

Documents the transition from the `socialsim4` package to `fos` (Future of Society).

---

## What Was Brought Over (Pipeline A)

Pipeline A is the structured game-theory experiment framework. All of these files were migrated and remain active:

| Area | Key files |
|------|-----------|
| Experiment engine | `core/experiment/` — `ExperimentScene`, `ExperimentAgent`, `ExperimentRunner`, `ExperimentConfig` |
| LLM layer | `core/llm/` — `LLMClient`, generation logic, OpenAI/Ollama/Gemini/mock providers |
| Backend API | `backend/api/` — Litestar routes, schemas, WebSocket handlers |
| Backend services | `backend/services/` — `SimTreeRuntime`, `ExportService`, session management |
| SimTree | `core/simtree.py` — branching timeline structure |
| Scenarios | `core/scenarios/` — `PrisonersDilemma`, `PublicGoods`, `CoordinationGame`, etc. |
| Registry | `core/registry.py` — scenario/scene lookup maps |
| Contagion | `core/contagion/` — SEIR state machine, `ContagionScene`, `ContagionState`, `StateTransition` |
| Information model | `core/experiment/information_model.py` — knowledge scoping (all/pair/self) |

---

## What Was Left Behind (Pipeline B)

Pipeline B was a free-form LLM simulation with bespoke scene types. It was not migrated.

| Component | Reason |
|-----------|---------|
| `Simulator` class | Replaced by `ExperimentRunner` in Pipeline A |
| `Agent` class (Pipeline B) | Replaced by `ExperimentAgent` |
| `Scene` base class (Pipeline B) | Replaced by `ExperimentScene` |
| `VillageScene` | Contained GameMap + physiology (hunger/energy) — physiology dropped, GameMap extracted |
| `WerewolfScene`, `LandlordScene` | Game-specific Pipeline B scenes — not applicable to Pipeline A |
| `GenericScene`, `SimpleChatScene`, `EmotionalConflictScene` | Pipeline B scene types — dropped |
| `CouncilScene` | Replaced by `CouncilExperiment` in Pipeline A |
| `LLMClientPool` | Replaced by per-client instantiation in Pipeline A |
| RAG / vector store layer | Not ported — was in `services/rag/`; no equivalent in fos yet |

---

## Structural Changes

### GameMap extracted to `fos.core.map.grid`

`GameMap`, `MapLocation`, and `Tile` previously lived inside `VillageScene` in socialsim4. They have been extracted to a standalone module at `src/fos/core/map/grid.py` with no Pipeline B dependencies.

- Excluded from extraction: `render_ascii`, `display_map` (both referenced the Pipeline B `Agent` class)
- Added: `get_all_locations()` method (required by ContagionScene interface)
- Import: `from fos.core.map.grid import GameMap, MapLocation, Tile`

### ContagionScene rewritten as standalone

`ContagionScene` previously inherited from `VillageScene`, pulling in all of Pipeline B's physiology (hunger, energy, inventory, time tracking). It has been rewritten as a standalone class:

- No longer inherits from `VillageScene` or any Pipeline B class
- `__init__`, `pre_run`, `serialize_config`, `deserialize_config` are all standalone (no `super()` calls)
- `get_agent_status_prompt` retains position and contagion state info; physiology lines removed
- Full SEIR state machine preserved: decay rules, proximity transmission, action transmission, Moore neighborhood

### Registry cleaned of Pipeline B entries

`INFORMATION_MODEL_MAP` and `SCENE_DESCRIPTIONS` in `core/registry.py` had seven dead Pipeline B entries (`village_scene`, `werewolf_scene`, `landlord_scene`, `generic_scene`, `simple_chat_scene`, `emotional_conflict_scene`, `council_scene`). These were removed. Active entries remain.

### simtree_runtime.py dead branch removed

The `village_scene` branch in `_build_scene` (which would have attempted `from fos.core.scenes.village_scene import GameMap`) was removed. Only `council_experiment` and `experiment_template` construction branches remain active.

### simtree.py graceful Pipeline B imports

`simtree.py` had module-level imports for `Simulator` and `LLMClientPool` (both Pipeline B). These now use `try/except ImportError` so `SimTree` is importable without Pipeline B present.

---

## Test Suite

After migration the test suite has 783 collected tests:

| Suite | Tests added | Status |
|-------|-------------|--------|
| `tests/integration/test_pipeline_contracts.py` | 7 | All passing |
| `tests/core/test_simtree.py` | 12 | All passing |
| `tests/unit/test_contagion_scene.py` | 17 | All passing |
| `tests/unit/test_contagion_rules.py` | 12 | All passing |
| `tests/unit/test_contagion_states.py` | 9 | All passing |

Pre-existing failures (31 failed + 2 errors) were present before this migration and are unrelated to the changes made here (confirmed by running the same tests against `main`).

---

## Known Issues

### R3 — ContagionScene not wired to backend (follow-up required)

`core/registry.py`'s `SCENE_MAP` only contains `council_experiment` and `experiment_template`. `ContagionScene` exists and is correct but is not reachable from the backend API:

- `SCENE_MAP` in `registry.py` needs a `"contagion_scene"` entry
- `simtree_runtime.py`'s `_build_scene` function needs a construction branch for `ContagionScene`
- This is a deliberate follow-up task — the class is ready, the wiring is not

### llm_config.py duplication

Two copies of `LLMConfig` exist:
- `src/fos/core/llm_config.py`
- `src/fos/core/llm/llm_config.py`

Both are importable. The pipeline contract tests use the shorter path `from fos.core.llm_config import LLMConfig`. These should be consolidated in a follow-up cleanup.

### RAG not ported

The RAG / vector store layer from socialsim4 was not ported. Any features relying on retrieval-augmented generation will need this layer re-implemented or replaced.

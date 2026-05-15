# Policy Cascade → Pipeline A Port Investigation

## Attribute compatibility

| Attribute | Used in (file:line) | ExperimentAgent has it? | Notes |
|-----------|---------------------|------------------------|-------|
| `agent.name` | Every file | YES | `name: str` field |
| `agent.properties` (dict) | base.py:378-382, distortion.py:33-37 | YES | `properties: Dict[str, Any]` field |
| `agent.properties.get("tier")` | base.py:378 | YES | Works via dict access |
| `agent.properties.get("政治职位层级")` | base.py:382 | YES | Works via dict access |
| `agent.role_prompt` | base.py:387, distortion.py:30 | YES | `role_prompt: str | None` field |
| `agent.user_profile` | base.py:388, distortion.py:31 | NO | ExperimentAgent has no `user_profile` field |
| `agent.language` | base.py:64 | NO | ExperimentAgent has no `language` field |
| `agent.consecutive_llm_errors` | base.py:113 | NO | ExperimentAgent has no `consecutive_llm_errors` field |
| `agent.is_offline` | base.py:114 | NO | ExperimentAgent has no `is_offline` field |
| `agent.short_memory` | base.py:115 | NO | ExperimentAgent has no `short_memory` field |
| `agent.short_memory.history` | base.py:115 | NO | Depends on short_memory |
| `agent.add_env_feedback(msg)` | runtime.py:167,309,313,... (15+ calls) | NO | ExperimentAgent has no `add_env_feedback` method |
| `agent.knowledge_base` | — (not directly accessed) | YES | `knowledge_base: List[Dict]` field |
| `agent.action_space` | — (not directly accessed) | NO | Not a field on ExperimentAgent |
| `agent.set_global_knowledge()` | — (not directly accessed) | NO | Not a method on ExperimentAgent |
| `agent.score` | — (not directly accessed) | YES | `score: int` field |
| `agent.provider_id` | — (not directly accessed) | YES | `provider_id: int | None` field |
| `getattr(agent, "role_prompt", "")` | base.py:387 | YES | Works with `getattr` |
| `getattr(agent, "user_profile", "")` | base.py:388 | Works (returns "") | `getattr` fallback works, but no data |
| `getattr(agent, "language", "")` | base.py:64 | Works (returns "") | `getattr` fallback works, but no data |
| `hasattr(agent, "properties")` | base.py:378 | YES | True for ExperimentAgent |

## Missing attributes — criticality analysis

### 1. `agent.add_env_feedback(msg)` — **CRITICAL**
- **Used in:** runtime.py (lines 167, 309, 313, 317, 346, 350, 354, 361, 379, 398, 414, 429), messages.py (line 437, 465)
- **Purpose:** Sends error/feedback messages back to the agent so they appear in the agent's prompt context for the next turn. This is the core feedback loop — when an agent's action is invalid, the error message is injected into their conversation.
- **ExperimentAgent equivalent:** None. ExperimentAgent doesn't have a feedback mechanism. In Pipeline A, the ExperimentRunner/ExperimentScene manages prompts differently via `RoundContextManager`.
- **Impact:** Without this, agents won't see error messages about invalid targets, missing messages, etc. They'll keep repeating invalid actions.

### 2. `agent.short_memory.history` — **HIGH**
- **Used in:** base.py:115 (inside `_reset_agents_for_new_policy`)
- **Purpose:** Iterates through memory entries to strip `[Action]` prefixes from assistant messages when a new policy is received.
- **ExperimentAgent equivalent:** None. ExperimentAgent has `action_history: List[Dict]` but it's a different concept.
- **Impact:** This is cleanup logic at the start of a new cascade. Without it, old action prefixes pollute the agent's context. Can be adapted or skipped for Pipeline A since ExperimentAgent doesn't use the same memory model.

### 3. `agent.consecutive_llm_errors` — **HIGH**
- **Used in:** base.py:113 (inside `_reset_agents_for_new_policy`)
- **Purpose:** Resets error counter to 0 when a new policy starts.
- **ExperimentAgent equivalent:** None.
- **Impact:** If not reset, stale error state could cause unexpected behavior. For Pipeline A, this attribute may not exist at all, so the reset would need to be conditional.

### 4. `agent.is_offline` — **MEDIUM**
- **Used in:** base.py:114 (inside `_reset_agents_for_new_policy`)
- **Purpose:** Resets offline flag to False when a new policy starts.
- **ExperimentAgent equivalent:** None.
- **Impact:** Same as consecutive_llm_errors — needs conditional handling.

### 5. `agent.user_profile` — **MEDIUM**
- **Used in:** base.py:388, distortion.py:31 (via `getattr(agent, "user_profile", "")`)
- **Purpose:** Used in tier extraction as a fallback to detect tier from profile text. Also used in distortion signal analysis.
- **ExperimentAgent equivalent:** No direct field. The `role_prompt` often contains the same information.
- **Impact:** Low because `getattr` with empty-string default means it degrades gracefully. Tier detection may fall through to other heuristics. Could map `user_profile` → `role_prompt` content.

### 6. `agent.language` — **LOW**
- **Used in:** base.py:64 (via `getattr(actor, "language", "")`)
- **Purpose:** Determines scene locale for i18n. Only used as a fallback after checking scene state.
- **ExperimentAgent equivalent:** None. Language is set per-scene in Pipeline A via config `locale`.
- **Impact:** Minimal — scene-level locale takes precedence, and `getattr` returns "" gracefully.

## Current wiring in simtree_runtime.py

### policy_cascade path (lines 326-570)

**Scene creation** (line 568-570):
```python
scene = scene_cls(name, initial_event_content)  # PolicyCascadeScene(name, initial_event_content)
if scene_key == "policy_cascade_scene" and hasattr(scene, "configure_from_config"):
    scene.configure_from_config(cfg)
```

**Agent creation** (lines 586-637):
- Uses `Agent.deserialize(agent_data)` — legacy Agent class
- Sets `name`, `user_profile`, `role_prompt`, `language`, `action_space`, `properties`, `knowledge_base`, `documents`
- These are ALL legacy Agent attributes

**Simulator creation** (after agent building):
- Creates legacy `Simulator` with these agents
- Uses `SequentialOrdering`
- Calls `simulator.scene = scene` and `scene.set_simulator(simulator)`

**Key observation:** The policy_cascade path uses the FULL legacy Simulator pipeline:
1. `Agent.deserialize()` → creates legacy Agent objects
2. `Simulator(agents, scene, ...)` → creates legacy Simulator
3. `SimTree.new(simulator, ...)` → wraps in SimTree

This is **NOT** using ExperimentRunnerAdapter at all.

## PolicyCascadeScene interface

### Inheritance chain
```
PolicyCascadeScene(
    PolicyCascadeRuntimeMixin,
    PolicyCascadePromptMixin,
    PolicyCascadeMessageMixin,
    PolicyCascadeFollowUpMixin,
    PolicyCascadeThreadMixin,
    PolicyCascadeStateMixin,
    PolicyCascadeDistortionMixin,
    PolicyCascadeBaseMixin,
    Scene,  ← LEGACY Scene base class
)
```

### Pipeline B methods (currently present)

The scene uses these **Pipeline B** methods:
- `get_scene_actions(agent)` — returns available actions for an agent
- `parse_and_handle_action(action_data, agent, simulator)` — processes agent actions
- `deliver_message(event, sender, simulator)` — routes messages between agents
- `post_turn(agent, simulator)` — after-turn bookkeeping
- `should_skip_turn(agent, simulator)` — determines if agent should be skipped
- `should_extend_run(turns, max_turns)` — extends simulation if needed
- `is_complete()` — checks if simulation is done
- `serialize_config()` / `deserialize_config()` — serialization
- `set_simulator(simulator)` — links scene to simulator
- `reset_for_run()` — resets state for new run
- `on_event(sim, event_type, data)` / `on_private_event(sim, event_type, data, recipients)` — event handling

### Pipeline A methods (what ExperimentScene uses)
- `initialize(llm_client, provider_clients)` — sets up agents and runner
- `run_round(event_callback)` — runs one round
- `serialize_config()` — serialization
- `is_complete()` — completion check

### Critical finding: `simulator` parameter everywhere
PolicyCascadeScene methods receive `simulator` as a parameter and use:
- `simulator.agents` — dict of agent objects (for iterating, looking up by name)
- `simulator.agents.keys()` — agent names
- `simulator.agents.values()` — agent objects
- `simulator.agents[name]` — specific agent lookup
- `simulator.turns` — turn counter
- `simulator.broadcast(event)` — broadcast to agents
- `simulator.broadcast(event, receivers=names)` — targeted broadcast
- `simulator.emit_event(type, data)` — emit system events
- `simulator.emit_event_later(type, data)` — deferred event emission

This is the **legacy Simulator interface**, not the ExperimentRunnerAdapter interface.

## experiment_template wiring pattern

### Scene creation (lines 402-468):
```python
inner_cfg = cfg.get("generic_config") or cfg
config = ExperimentConfig(
    agents=agent_config.get("agents", []),
    actions=inner_cfg.get("actions", []),
    parameters=inner_cfg.get("parameters", {}),
    description=...,
    scenario_id=...,
    round_visibility=...,
    social_network=...,
    locale=...,
)
scene = ExperimentScene(config)
adapter = ExperimentRunnerAdapter(scene, clients or make_clients_from_env())
return SimTree.new(adapter, adapter.clients)
```

### Key differences from policy_cascade path:
1. **No `Agent.deserialize()`** — agents created from config in `ExperimentScene.initialize()`
2. **No legacy Simulator** — `ExperimentRunnerAdapter` replaces it
3. **No `scene.set_simulator()`** — scene is self-contained
4. **Agent building is config-driven** — raw agent config dicts passed to ExperimentScene

## Port complexity assessment

**Complex** — This port requires significant redesign because:

1. **Missing base classes:** Both `fos.core.scene.Scene` and `fos.core.agent.Agent` modules don't exist. They were never migrated from socialsim4. PolicyCascadeScene can't even be imported currently.

2. **Deep Simulator coupling:** The scene uses `simulator.agents`, `simulator.broadcast()`, `simulator.emit_event()`, `simulator.turns` in 30+ locations across 8 files. These aren't simple attribute reads — they're method calls that drive the simulation.

3. **Legacy agent attribute dependencies:** `add_env_feedback()`, `short_memory.history`, `consecutive_llm_errors`, `is_offline` are structural — they assume agents manage their own conversation history, not the runner.

4. **Pipeline B lifecycle:** The scene uses `get_scene_actions(agent)`, `parse_and_handle_action()`, `deliver_message()`, `post_turn()`, `should_skip_turn()` — these are Pipeline B orchestration methods. Pipeline A uses `initialize()` / `run_round()` instead.

5. **8 mixin files with ~2400 lines total** — all deeply coupled to the legacy Agent/Simulator interfaces.

## Recommended approach

### Phase 1: Create missing base modules (prerequisite)

1. **Create `src/fos/core/scene.py`** — Minimal Scene base class with:
   - `__init__(name, initial_event)` — sets `self.name`, `self.initial_event`, `self.state = {}`
   - `set_simulator(simulator)` — stores reference
   - Empty stubs for Pipeline B methods (`get_scene_actions`, `parse_and_handle_action`, `deliver_message`, `post_turn`, `should_skip_turn`, `should_extend_run`, `is_complete`, `serialize_config`, `on_event`)

2. **Create `src/fos/core/agent.py`** — Minimal Agent class with:
   - `__init__` / `deserialize()` factory
   - `name`, `properties`, `role_prompt`, `user_profile`, `language`, `action_space`, `knowledge_base` attributes
   - `add_env_feedback(msg)` method
   - `short_memory` object with `.history` list
   - `consecutive_llm_errors`, `is_offline` attributes
   - This makes policy_cascade importable and functional in Pipeline B mode

### Phase 2: Port Strategy Decision

**Option A (Recommended): Keep PolicyCascadeScene as Pipeline B, create PolicyCascadeExperimentScene for Pipeline A**

- Create a new `PolicyCascadeExperimentScene` that subclasses `ExperimentScene`
- Override `initialize()`, `run_round()`, `is_complete()` to implement the cascade logic
- Map legacy `simulator.agents` → `self.agents` (ExperimentAgent list)
- Map legacy `simulator.broadcast()` → experiment event emission
- Map legacy `agent.add_env_feedback()` → prompt context injection via RoundContextManager
- Reuse the mixin logic (tier extraction, distortion, threads) since most of it operates on `agent.name` and `agent.properties` which ExperimentAgent has
- Wire in `simtree_runtime.py` alongside existing policy_cascade path

**Option B (Alternative): Shim ExperimentRunnerAdapter to look like legacy Simulator**

- Make ExperimentRunnerAdapter expose `agents` dict, `broadcast()`, `emit_event()`, `turns`
- Create a thin wrapper agent that has `add_env_feedback()`, `short_memory`, etc. backed by ExperimentAgent
- This lets PolicyCascadeScene run unmodified through the adapter
- Higher risk — impedance mismatch between Pipeline A and B lifecycle

### Phase 3: Wiring changes in simtree_runtime.py (following Option A)

1. Add `"policy_cascade_experiment"` to the scene registry
2. Add new `elif scene_key == "policy_cascade_experiment":` branch:
   - Build `ExperimentConfig` from cfg (tier_order, cascade_mode, distortion params)
   - Create `PolicyCascadeExperimentScene(config)`
   - Wrap in `ExperimentRunnerAdapter(scene, clients)`
   - Return `SimTree.new(adapter, adapter.clients)`
3. Agent config stays as raw dicts — ExperimentScene.initialize() creates ExperimentAgents

### Phase 4: Missing attribute bridging

For the attributes ExperimentAgent lacks:

| Attribute | Bridge strategy |
|-----------|----------------|
| `add_env_feedback()` | Add to ExperimentAgent as a simple feedback buffer; consume in prompt building |
| `short_memory.history` | Add a `_memory_history: list[dict]` field; or skip the cleanup logic since Pipeline A manages prompts differently |
| `consecutive_llm_errors` | Add as `int` field; or make _reset_agents_for_new_policy conditional |
| `is_offline` | Add as `bool` field; same as above |
| `user_profile` | Map from `role_prompt` content; or add field |
| `language` | Derive from scene `locale`; or add field |

### Implementation order

1. Create `src/fos/core/scene.py` (minimal base)
2. Create `src/fos/core/agent.py` (minimal legacy Agent)
3. Verify policy_cascade imports and runs in Pipeline B mode
4. Add missing attributes to ExperimentAgent (add_env_feedback, etc.)
5. Create `PolicyCascadeExperimentScene(ExperimentScene)`
6. Move/adapt mixin logic for Pipeline A lifecycle
7. Wire in simtree_runtime.py
8. Integration test

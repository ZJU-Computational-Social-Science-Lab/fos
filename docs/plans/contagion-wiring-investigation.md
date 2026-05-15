# ContagionScene Backend Wiring — Investigation

## What needs to change (summary)

Three files need changes to make ContagionScene reachable from the frontend:

1. **`src/fos/core/registry.py`** — Add `ContagionScene` to `SCENE_MAP`, `SCENE_ACTIONS`, `INFORMATION_MODEL_MAP`, and `SCENE_DESCRIPTIONS`
2. **`src/fos/backend/services/simtree_runtime.py`** — Add an `elif scene_key == "contagion_scene":` branch in `_build_tree_for_sim()` that constructs `ContagionScene` with the correct args from `cfg` parameters
3. **`src/fos/backend/api/routes/scenes.py`** — Add a `scene_config_template()` handler for `contagion_scene` that provides the config schema (grid_size, rules, initial_infected)

Additionally, the scenario registry already has a `contagion` scenario entry (in `src/fos/core/scenarios/registry.py`) — no changes needed there.

---

## Registry changes needed (`src/fos/core/registry.py`)

### SCENE_MAP

```python
from fos.core.contagion.scene import ContagionScene

SCENE_MAP = {
    "council_experiment": CouncilExperimentScene,
    "experiment_template": ExperimentScene,
    "contagion_scene": ContagionScene,  # NEW
}
```

### SCENE_ACTIONS

```python
SCENE_ACTIONS = {
    # ... existing entries ...
    "contagion_scene": {
        "basic": ["move_adjacent", "speak_to"],
        "allowed": [],
    },
}
```

### INFORMATION_MODEL_MAP

```python
"contagion_scene": InformationModel(scope_type="neighborhood", recent_window=3, include_scores=False),
```

### SCENE_DESCRIPTIONS

```python
"contagion_scene": "SEIR contagion dynamics on a grid. Agents spread infection through proximity and social interactions, with configurable transmission rates and recovery.",
```

---

## simtree_runtime.py changes needed

### Exact elif branch to add (inside `_build_tree_for_sim`, around line 516)

Insert **before** the `else:` fallback (line 516):

```python
elif scene_key == "contagion_scene":
    from fos.core.contagion.scene import ContagionScene
    from fos.core.contagion.states import ContagionState
    from fos.core.contagion.rules import StateTransition
    from fos.core.map.grid import GameMap

    params = cfg.get("parameters", {})

    # Grid setup
    grid_size = int(params.get("grid_size", 10))
    game_map = GameMap(width=grid_size, height=grid_size)

    # Build transition rules from scenario parameters
    proximity_prob = float(params.get("proximity_probability", 0.3))
    action_prob = float(params.get("action_probability", 0.5))
    recovery_turns = int(params.get("recovery_turns", 5))
    initial_infected = int(params.get("initial_infected", 1))

    rules = [
        # Susceptible → Infected via proximity (adjacent agents)
        StateTransition(
            from_state=ContagionState.SUSCEPTIBLE,
            to_state=ContagionState.INFECTED,
            trigger_type="proximity",
            probability=proximity_prob,
        ),
        # Susceptible → Infected via action (speak_to targeted agent)
        StateTransition(
            from_state=ContagionState.SUSCEPTIBLE,
            to_state=ContagionState.INFECTED,
            trigger_type="action",
            probability=action_prob,
        ),
        # Infected → Recovered via decay (after N turns)
        StateTransition(
            from_state=ContagionState.INFECTED,
            to_state=ContagionState.RECOVERED,
            trigger_type="decay",
            probability=1.0,  # Guaranteed after delay
            decay_turns=recovery_turns,
        ),
    ]

    scene = ContagionScene(
        name=name,
        initial_event=initial_event_content,
        game_map=game_map,
        rules=rules,
        initial_infected_count=initial_infected,
    )
```

### Config dict shape the frontend sends

The contagion scenario's `parameters` array in the registry defines these keys:
- `initial_infected` (int, default 1)
- `proximity_probability` (float, default 0.3)
- `action_probability` (float, default 0.5)
- `recovery_turns` (int, default 5)
- `grid_size` (int, default 10)

These arrive in `cfg["parameters"]` (nested under `scene_config` on the sim_record).

---

## ContagionScene constructor requirements

**Signature** (from `src/fos/core/contagion/scene.py:37`):

```python
def __init__(
    self,
    name: str,
    initial_event: str,
    game_map: GameMap,
    rules: List[StateTransition],
    initial_infected_count: int = 1,
):
```

### What each arg needs:

| Arg | Type | Source |
|-----|------|--------|
| `name` | `str` | `sim_record.name` or `scene_type` |
| `initial_event` | `str` | Resolved from `cfg.initial_event` / `cfg.initial_events` / `cfg.description` |
| `game_map` | `GameMap` | Constructed from `cfg.parameters.grid_size` → `GameMap(width=N, height=N)` |
| `rules` | `List[StateTransition]` | Built from `cfg.parameters` (proximity_probability, action_probability, recovery_turns) |
| `initial_infected_count` | `int` | `cfg.parameters.initial_infected` (default 1) |

### Factory methods:

- **`deserialize_config(cls, config: dict) -> dict`** — Returns constructor kwargs dict (does NOT return an instance). Parses `game_map` and `rules` from serialized format. Can be used for deserialization.
- **`serialize_config(self) -> dict`** — Returns full config dict for persistence.
- No `from_scenario_config` method exists.

---

## scenes.py changes needed

Add a handler for `contagion_scene` in `scene_config_template()`:

```python
if scene_key == "contagion_scene":
    from fos.core.map.grid import GameMap
    default_map = GameMap(width=10, height=10)
    return {
        "type": scene_key,
        "name": "ContagionScene",
        "description": SCENE_DESCRIPTIONS.get(scene_key, ""),
        "config_schema": {
            "parameters": {
                "initial_infected": 1,
                "proximity_probability": 0.3,
                "action_probability": 0.5,
                "recovery_turns": 5,
                "grid_size": 10,
            },
            "initial_events": [],
        },
        "allowed_actions": [],
        "basic_actions": ["move_adjacent", "speak_to"],
    }
```

---

## Unknowns / questions

1. **Should contagion use the Pipeline B Simulator or a custom adapter?** ContagionScene uses `pre_run`, `pre_turn_rules`, and `get_scene_actions` — these are the same hooks the legacy Simulator calls. The existing fallback branch (`scene = scene_cls(name, initial_event_content)` at line 517) creates a standard Simulator. This should work because ContagionScene follows the same scene protocol. No adapter needed.

2. **Agent placement on the grid:** ContagionScene reads `agent.properties["map_xy"]` for positions. The current `_build_tree_for_sim` code does NOT set `map_xy` on agents. We need to either:
   - Randomly place agents on the grid when constructing the tree (add `map_xy` to each agent's properties), OR
   - Have `ContagionScene.pre_run()` assign random positions if none exist

3. **Scenario flow via experiment_template vs. dedicated scene key:** The contagion scenario is currently routable through `experiment_template` (scenario_id="contagion"). That path uses `ExperimentScene`, NOT `ContagionScene`. These are completely different implementations. The question is: should we keep the experiment_template path as a fallback, or should `contagion` scenario_id always route to `contagion_scene`?

4. **Deserialization support:** `ExperimentRunnerAdapter.deserialize` doesn't know about contagion_scene. If we want save/resume support, `SimTree.deserialize` needs a path to reconstruct ContagionScene. This is a follow-up concern, not blocking for initial wiring.

---

## Suggested wiring approach

Add `contagion_scene` as a new Pipeline A entry in SCENE_MAP and handle it in `_build_tree_for_sim` with a dedicated elif branch. The branch constructs `ContagionScene` from the scenario's `parameters` dict (grid_size, transmission rates, recovery_turns), builds the `StateTransition` rules, and falls through to the standard Simulator path (the existing agent-building code at lines 534+). This is the same pattern used by `landlord_scene`, `werewolf_scene`, and `generic_scene` — minimal change, no new abstractions, and no impact on the existing `experiment_template` → contagion path. The one missing piece is agent grid placement: add a small block after scene construction that randomly assigns `map_xy` to each agent within the game_map bounds.

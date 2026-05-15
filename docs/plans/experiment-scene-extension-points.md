# ExperimentScene Extension Points

## Post-action hook

After an agent's action is dispatched (via `runner.execute_action`), the following happens inside `ExperimentScene.run_round()` (scene.py:292-302):

1. **`runner.execute_action(action_name, agent_name, params, self.state, self)`** is called. This delegates to `ActionHandler.execute()`, which either calls the action's `handler` function or applies declarative effects via `_apply_effects`.
2. The result is checked for success/failure and stored in `exec_results`.
3. After all actions are processed, events are emitted via `event_emitter("experiment_action", event_data)`.
4. A **phase transition hook** is checked: `self.facilitator.check_and_transition_phase(round_num)` (scene.py:362-365) — but only if a `facilitator` attribute exists with that method.

There is **no generic `post_action` or `on_action_complete` method** that a subclass could override. The action dispatch → state mutation → event emission pipeline is a straight-line sequence inside `run_round()`.

## Payoff engine call site

The payoff engine (`PayoffEngine`) is called **per-round, not per-action**.

**Exact call site:** `runner.py:316` inside `ExperimentRunner._calculate_scores()`:

```python
round_payoffs = self.payoff_engine.calculate_round_payoffs(
    payoff_type=payoff_type,
    actions=round_actions,
    config=payoff_config,
    grouping_mode=grouping_mode,
    graph=graph,
    state=current_state,
)
```

This method is called from every round-mode method:
- `_run_simultaneous_round` (line 473)
- `_run_sequential_round` (line 539)
- `_run_random_round` (line 602)
- `_run_paired_round` (line 702)

The call always happens **after all agents have acted** and **before events are recorded to context**.

## Overridable methods

Methods that look designed for (or amenable to) subclass override:

| Method | Class | Signature | Purpose |
|--------|-------|-----------|---------|
| `run_round()` | ExperimentScene | `(self, event_emitter) -> RoundResult` | Main per-round entry point — could wrap or replace payoff logic |
| `initialize()` | ExperimentScene | `(self, llm_client, provider_clients)` | Agent creation + runner setup — override to inject custom runners |
| `_initialize_state()` | ExperimentScene | `(self)` | State initialization — override for custom agent state |
| `_create_game_config()` | ExperimentScene | `(self) -> GameConfig` | Builds game config — override to change payoff_type, actions, etc. |
| `_build_payoff_summary()` | ExperimentScene | `(self) -> str` | Prompt text for payoffs — override for custom payoff display |
| `_build_params_section()` | ExperimentScene | `(self) -> str` | Prompt text for params — override for custom scenario descriptions |
| `_build_context_summary()` | ExperimentScene | `(self) -> str` | Round history text — override for custom history format |
| `get_scene_actions()` | ExperimentScene | `(self, agent_name) -> list[str] \| None` | Action filtering — override for phase-based actions |
| `serialize_config()` | ExperimentScene | `(self) -> dict` | Persistence — override to add custom state |
| `deserialize_config()` | ExperimentScene | `(cls, data) -> ExperimentScene` | Restoration — override to restore custom state |
| `_calculate_scores()` | ExperimentRunner | `(self, round_actions, pairs=None) -> Dict[str, int\|float]` | **The payoff calculation** — override to replace payoff with SEIR |
| `_apply_coordination_feedback()` | ExperimentRunner | `(self, actions, round_num)` | Post-round feedback — override for custom feedback |
| `execute_action()` | ExperimentRunner | `(self, action_name, agent_name, params, state, scene=None)` | Action dispatch — delegates to ActionHandler |

**Key observation:** The runner is constructed inside `ExperimentScene.initialize()` and stored as `self.runner`. The scene does **not** pass itself as a "payoff strategy" — it hardcodes `PayoffEngine` inside the runner's `__init__` (runner.py:107).

## Verdict

**A `ContagionScene` subclassing `ExperimentScene` could NOT replace payoff with SEIR by overriding just one method.** Here's why:

The payoff calculation lives in `ExperimentRunner._calculate_scores()`, not on `ExperimentScene` itself. To replace it, you would need to either:

1. **Override `initialize()`** to inject a custom `ExperimentRunner` subclass that overrides `_calculate_scores()` — this replaces the payoff engine call with SEIR state transitions. But you'd also need to handle the fact that `_calculate_scores` is called from 4 separate `_run_*_round` methods (simultaneous, sequential, random, paired), and they all update `agent.score` from the result.

2. **Override `run_round()`** entirely to intercept after `runner._run_single_round()` returns and replace the payoff in the `RoundResult` — but the runner has already called `_calculate_scores` internally by that point.

3. **Override `_create_game_config()`** to set `payoff_type="none"` (disabling payoff), then add SEIR logic in a custom `run_round()` override that processes actions after the runner returns.

The cleanest path is **option 3**: subclass `ExperimentScene`, override `_create_game_config()` to set `payoff_type="none"`, and override `run_round()` to call `super().run_round()` then apply SEIR transitions to `self.state` based on the round's actions. This keeps the runner's round execution intact while replacing the scoring semantics entirely. You'd also want to override `_build_payoff_summary()` to show SEIR rules instead of payoff tables.

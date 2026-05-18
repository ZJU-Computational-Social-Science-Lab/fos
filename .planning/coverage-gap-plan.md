# Test Coverage Gap Plan — fos.core

**Generated:** 2026-05-18
**Baseline:** 874 tests passing, 53% line coverage, 283 branch coverage
**Goal:** Fill meaningful coverage gaps — tests that catch bugs which silently corrupt simulation results.

---

## How to Read This Plan

Each section covers one module. For each module:
- **Why it matters** — what class of bugs hide here
- **What exists** — tests already written
- **What to write** — specific test cases grouped by feature
- **Mock infrastructure** — what fixtures/stubs you'll need
- **File to create** — where the new tests go

Tests are ordered by priority within each module. Write them top-to-bottom.

---

## Skip List — Do NOT Write Tests For These

These are Pipeline B stubs, legacy code being replaced, or test doubles:

| Module | Why Skip |
|--------|----------|
| `core/agent/__init__.py` (35%) | Pipeline B stub, marked TODO: delete |
| `core/scene.py` (50%) | Pipeline B stub |
| `core/simulator.py` (10%) | Pipeline B stub |
| `core/llm/providers/mock.py` (24%) | Test double itself |
| `core/map/grid.py` (25%) | Simple spatial indexing, low bug risk |
| `core/scenes/policy_cascade/runtime.py` (9%) | Legacy, being replaced |
| `core/scenes/policy_cascade/threads.py` (11%) | Legacy, being replaced |
| `core/scenes/policy_cascade/messages.py` (16%) | Legacy, being replaced |
| `core/scenes/policy_cascade/followup.py` (18%) | Legacy, being replaced |
| `core/scenes/policy_cascade/state.py` (23%) | Legacy, being replaced |
| `core/scenes/policy_cascade/base.py` (33%) | Legacy, being replaced |
| `core/scenes/policy_cascade/prompts.py` (3%) | Hard-coded prompts being replaced by i18n |

---

## Module 1: `core/simtree.py` — 18% (487 stmts)

### Why It Matters

SimTree manages branching "what-if" timelines. A bug in `branch()` can mean two supposedly-independent timelines share an LLM client pool or agent state, producing **correlated results that look like real effects**. This is the single most dangerous untested module — bugs here silently invalidate research.

### What Exists

`tests/core/test_simtree.py` — covers only structural methods: `leaves()`, `max_depth()`, `frontier()`, `lca()`, `summaries()`. No tests for cloning, branching, serialization, or event handling.

### What to Write

**File:** `tests/core/test_simtree_operations.py`

#### Mock Infrastructure Needed

```python
class FakeSim:
    """Minimal simulator mock for SimTree tests."""
    def __init__(self, agents=None):
        self.agents = agents or {}
        self.scene = MockScene()
        self.event_queue = MockEventQueue()
        self.ordering = MockOrdering()
        self.turns = 0
        self._log_event = None

    def serialize(self):
        return {"agents": {n: {"name": n} for n in self.agents},
                "scene": {"TYPE": "mock"}, "turns": self.turns}

    @classmethod
    def deserialize(cls, data, clients, log_handler=None):
        sim = cls()
        sim.agents = {n: MockAgent(n) for n in data.get("agents", {})}
        return sim

    def run(self, max_turns):
        self.turns += max_turns

    def reset_event_queue(self):
        pass

    def broadcast(self, event):
        pass

    def emit_remaining_events(self):
        pass

class MockAgent:
    def __init__(self, name):
        self.name = name
        self.short_memory = MockMemory()
        self.plan_state = None
        self.properties = {}
        self.knowledge_base = []
        self.documents = {}
        self.language = "en"
        self.last_history_length = 1
        self.consecutive_llm_errors = 0
        self.is_offline = False
        self.log_event = None
        self.role_prompt = ""
        self.user_profile = ""

    def add_env_feedback(self, msg):
        pass

class MockMemory:
    def __init__(self):
        self.history = []
    def get_all(self):
        return self.history
    def append(self, role, content):
        self.history.append({"role": role, "content": content})

class MockScene:
    def __init__(self):
        self.TYPE = "mock"
        self.state = {}
        self.config = MockConfig()
        self.runner = None

class MockConfig:
    def __init__(self):
        self.parameters = {}
        self.description = ""
        self.social_network = {}
        self.actions = []

class MockOrdering:
    def serialize(self):
        return {"type": "mock_ordering", "state": {}}

class MockEventQueue:
    def empty(self):
        return True
```

#### Test Cases

**Group A: `SimTree.new()` — Root node creation (9 tests)**
1. `test_new_creates_root_node_with_id_zero` — root.id == 0, depth == 0
2. `test_new_root_has_no_parent` — root.parent is None, edge_type == "root"
3. `test_new_clones_simulator_via_serialize_deserialize` — root.sim is not the original sim
4. `test_new_root_agents_have_reset_history_length` — agent.last_history_length == len(memory) - 1
5. `test_new_root_agents_have_reset_error_counters` — consecutive_llm_errors == 0, is_offline == False
6. `test_new_root_sim_has_reset_event_queue` — event_queue.empty() is True
7. `test_new_initializes_tree_structure` — tree.nodes has 1 entry, tree.root == 0, tree._seq == 0
8. `test_new_with_client_pool_uses_pool` — passes use_client_pool=True, verify pool is used
9. `test_new_attaches_log_handler` — root.sim._log_event is not None

**Group B: `_check_simulator_clone()` — Independence validation (10 tests)**
10. `test_clone_check_passes_for_independent_clones` — two separate FakeSim instances
11. `test_clone_check_fails_if_agents_dict_shared` — same dict object (id check)
12. `test_clone_check_fails_if_scene_shared` — same scene object
13. `test_clone_check_fails_if_event_queue_shared` — same queue object
14. `test_clone_check_fails_if_ordering_shared` — same ordering object
15. `test_clone_check_fails_if_agent_names_differ` — different agent sets
16. `test_clone_check_fails_if_cloned_event_queue_not_empty` — queue with items
17. `test_clone_check_fails_if_agent_count_differs` — different number of agents
18. `test_clone_check_fails_if_scene_type_differs` — different TYPE strings
19. `test_clone_check_skips_for_experiment_runner_adapter` — ExperimentRunnerAdapter instances bypass checks

**Group C: `branch()` — Core branching with operations (12 tests)**
20. `test_branch_from_root_creates_child` — sibling of root becomes child
21. `test_branch_from_nonroot_creates_sibling` — shares grandparent
22. `test_branch_with_agent_ctx_append_adds_to_memory` — agent.short_memory has new entry
23. `test_branch_with_agent_plan_replace_sets_plan` — agent.plan_state updated
24. `test_branch_with_agent_props_patch_updates_properties` — merge into agent.properties
25. `test_branch_with_scene_state_patch_updates_scene_state` — scene.state patched
26. `test_branch_with_config_params_patch_merges_parameters` — config.parameters merged
27. `test_branch_with_network_replace_sets_social_network` — config.social_network updated
28. `test_branch_with_public_broadcast_calls_broadcast` — sim.broadcast called with PublicEvent
29. `test_branch_with_environment_event_adds_feedback_to_all_agents` — all agents get feedback
30. `test_branch_with_environment_event_targets_specific_receivers` — only named agents get feedback
31. `test_branch_with_unknown_operation_raises_valueerror` — invalid op type

**Group D: `copy_sim()` / `attach()` — Node creation and linking (8 tests)**
32. `test_copy_sim_creates_new_node_with_unique_id` — id increments
33. `test_copy_sim_deep_copies_parent_logs` — logs are json-roundtripped copy
34. `test_copy_sim_from_missing_node_raises_keyerror` — bad node_id
35. `test_attach_links_child_to_parent` — parent.children contains child id
36. `test_attach_sets_edge_type_from_ops` — single op maps to correct edge_type
37. `test_attach_classifies_multi_ops_as_multi` — multiple ops → edge_type="multi"
38. `test_attach_sets_depth_to_parent_plus_one` — child.depth == parent.depth + 1
39. `test_attach_with_missing_parent_raises_keyerror` — bad parent_id

**Group E: `advance()` / `advance_frontier()` / `advance_selected()` (6 tests)**
40. `test_advance_runs_simulator_for_turns` — sim.turns incremented
41. `test_advance_creates_child_with_advance_op` — edge_type == "advance"
42. `test_advance_frontier_advances_all_max_depth_leaves` — all frontier nodes get children
43. `test_advance_selected_advances_only_specified_nodes` — only listed parents
44. `test_advance_frontier_respects_only_max_depth_false` — all leaves, not just max-depth
45. `test_advance_selected_with_empty_list_returns_empty` — no-op

**Group F: Serialization round-trip (4 tests)**
46. `test_serialize_includes_all_node_data` — root id, seq, nodes with sim/logs/meta/ops
47. `test_deserialize_rebuilds_tree_structure` — children mapping restored
48. `test_deserialize_restores_log_handlers` — all nodes have log_event set
49. `test_serialize_deserialize_roundtrip_preserves_structure` — serialize→deserialize→serialize matches

**Group G: Subscription and deletion (6 tests)**
50. `test_add_node_sub_creates_subscription` — subscriber queue added to node
51. `test_remove_node_sub_cleans_up` — subscriber removed, empty nodes cleaned
52. `test_clear_node_subs_removes_all_for_node` — all subscribers cleared
53. `test_delete_subtree_removes_node_and_descendants` — nodes dict cleaned
54. `test_delete_subtree_cleans_up_subscriptions` — _node_subs cleaned
55. `test_delete_subtree_raises_for_root` — ValueError on node_id=0

**Group H: `apply_agent_overrides()` (4 tests)**
56. `test_override_language_sets_agent_language` — agent.language updated, stored in meta
57. `test_override_properties_merges_into_existing` — new props merged
58. `test_override_knowledge_base_deep_copies` — no shared references
59. `test_override_on_missing_node_raises_keyerror` — bad node_id

---

## Module 2: `core/contagion/scene.py` — 63% (188 stmts)

### Why It Matters

The contagion scene simulates SEIR (Susceptible-Exposed-Infected-Recovered) dynamics. The uncovered code is the **actual infection mechanics** — probability calculations, bidirectional transmission, recovery timing. If these are wrong, the entire contagion study produces invalid infection rate data.

### What Exists

Integration tests in `tests/` cover basic instantiation, agent placement, initial infection, round completion, and Moore neighborhood geometry. No tests exercise the actual transmission logic.

### What to Write

**File:** `tests/core/contagion/test_contagion_transmission.py`

#### Mock Infrastructure Needed

```python
def make_contagion_agent(name, state="susceptible", turns_infected=0, map_xy=None):
    """Create a minimal agent for contagion testing."""
    agent = Mock()
    agent.name = name
    agent.properties = {
        "contagion_state": state,
        "contagion_turns": turns_infected,
    }
    if map_xy is not None:
        agent.properties["map_xy"] = map_xy
    return agent

def make_contagion_scene(agents=None, rules=None, grid_size=5):
    """Create a ContagionScene with deterministic config."""
    # Use scene config with fixed seed for deterministic tests
    ...
```

#### Test Cases

**Group A: Action-based transmission via speak_to (6 tests)**
1. `test_infected_sender_infects_susceptible_target_via_speak_to` — I→S with probability=1.0
2. `test_susceptible_sender_infected_by_target_via_speak_to` — bidirectional S←I
3. `test_already_transitioned_agent_not_re_infected_same_round` — transitioned set prevents doubles
4. `test_failed_speak_to_action_does_not_transmit` — action.success=False
5. `test_skipped_action_does_not_transmit` — action.skipped=True
6. `test_non_speak_to_action_does_not_trigger_transmission` — e.g. "move" action

**Group B: Proximity-based transmission (4 tests)**
7. `test_adjacent_infected_agent_transmits_to_susceptible_with_prob_1` — Moore neighbor with p=1.0
8. `test_non_adjacent_agent_does_not_transmit_via_proximity` — distant agent, p=1.0, no infection
9. `test_agent_without_map_xy_skipped_in_proximity_loop` — no crash, no infection
10. `test_multiple_infected_neighbors_each_have_independent_chance` — 2 infected neighbors

**Group C: Decay/recovery timing (4 tests)**
11. `test_infected_agent_recovers_after_decay_turns` — set decay_turns=2, run 2 rounds
12. `test_agent_does_not_recover_before_decay_turns_elapsed` — decay_turns=3, run 2 rounds
13. `test_susceptible_agent_never_decays` — no state change for susceptible
14. `test_exposed_agent_transitions_to_infected` — E→I transition

**Group D: Grid helpers (4 tests)**
15. `test_get_adjacent_agents_returns_moore_neighbors` — agent at (2,2) on 5x5 grid
16. `test_get_adjacent_agents_returns_empty_for_nonexistent_agent` — agent name not in agents
17. `test_get_adjacent_agents_returns_empty_for_agent_without_position` — no map_xy
18. `test_get_adjacent_agents_excludes_self` — queried agent not in result

**Group E: Initialization edge cases (3 tests)**
19. `test_agents_without_map_xy_get_random_positions_within_grid_bounds` — verify 0 <= x < grid_size
20. `test_agents_with_existing_map_xy_keep_their_positions` — no overwrite
21. `test_decay_turns_extracted_from_rules_and_added_to_params` — rules with trigger_type="decay"

**Group F: Deserialization (2 tests)**
22. `test_deserialize_config_restores_scene_with_correct_grid_dimensions` — game_map rebuilt
23. `test_deserialize_config_with_missing_optional_fields_uses_defaults` — graceful degradation

---

## Module 3: `core/experiment/scene.py` — 74% (482 stmts)

### Why It Matters

ExperimentScene orchestrates multi-agent experiments. The uncovered paths include payoff matrix calculation, deduction budget validation, and parameter formatting for different scenario types. Bugs here mean **wrong payoff numbers** or **agents getting wrong context**.

### What Exists

`tests/unit/experiment/test_experiment_scene_state.py` — covers initialization, state persistence, resource management, round execution, coordination games, custom action parameters, PGG phase transitions. Happy path is well-covered.

### What to Write

**File:** `tests/unit/experiment/test_experiment_scene_edge_cases.py`

#### Test Cases

**Group A: LLM client distribution edge cases (2 tests)**
1. `test_agent_with_unknown_dialect_falls_back_to_default_client` — dialect not in known set
2. `test_agent_with_llm_config_missing_dialect_attribute_uses_default` — config object without dialect

**Group B: Information model upgrade (2 tests)**
3. `test_multi_agent_pd_game_upgrades_scope_to_pair` — 3+ agents with PD payoffs → pair scope
4. `test_information_model_upgrade_preserves_show_average_contribution` — param carried over

**Group C: Action execution failures (1 test)**
5. `test_failed_action_execution_marks_unsuccessful_and_populates_error` — execute_action returns failure

**Group D: Custom action names and payoff matrix (3 tests)**
6. `test_action_1_action_2_parameters_override_default_action_names` — custom names in config
7. `test_matrix_cells_remapped_for_custom_action_names` — payoff keys updated
8. `test_description_template_formatted_with_custom_action_params` — template interpolation

**Group E: Deduction budget (2 tests)**
9. `test_reduce_action_added_when_deduction_budget_positive` — deduction_budget_per_phase > 0
10. `test_reduce_action_not_added_when_deduction_budget_zero` — deduction_budget_per_phase == 0

**Group F: Sociology parameter formatting (3 tests)**
11. `test_social_norm_disruption_generates_correct_param_text` — norm_strength formatting
12. `test_resource_scarcity_generates_correct_param_text` — resource_amount and distribution
13. `test_council_generates_correct_param_text` — council-specific params

**Group G: Discussion followup detection (2 tests)**
14. `test_discussion_scenario_gets_plain_text_followup_for_speak` — council_chamber type
15. `test_custom_scenario_with_speak_action_auto_detected` — speak in action list

**Group H: Council facilitator phase transition (1 test)**
16. `test_scene_with_facilitator_calls_check_and_transition_phase` — after round completion

**Group I: Parameter description interpolation (2 tests)**
17. `test_parameter_description_interpolates_scenario_params` — successful formatting
18. `test_parameter_description_interpolation_failure_does_not_crash` — KeyError silently caught

**Group J: Payoff text formatting (2 tests)**
19. `test_pd_payoff_summary_includes_all_four_parameters` — cooperate_reward, etc.
20. `test_non_pd_scenario_gets_generic_parameter_display` — title-cased labels

---

## Module 4: `core/context_builder.py` — 81% (143 stmts)

### Why It Matters

ContextBuilder assembles the text that gets sent to the LLM. If it shows the wrong history or wrong neighbor actions, agents respond to **wrong information** and the simulation produces garbage results that look valid.

### What Exists

`tests/core/test_context_builder.py` and `tests/core/test_context_builder_average.py` — cover basic context assembly and average contribution display.

### What to Write

**File:** `tests/core/test_context_builder_visibility.py`

#### Test Cases

**Group A: Sequential visibility mode (3 tests)**
1. `test_sequential_mode_agent_sees_earlier_agents_current_round` — agent B sees A's action, not C's
2. `test_sequential_mode_first_agent_sees_no_current_round_actions` — alphabetically first
3. `test_sequential_mode_last_agent_sees_all_current_round_actions` — alphabetically last

**Group B: Previous rounds visibility (2 tests)**
4. `test_previous_rounds_mode_shows_only_completed_rounds` — current round excluded
5. `test_previous_rounds_with_no_history_returns_first_round_message` — empty filtered_history

**Group C: Average contribution edge cases (3 tests)**
6. `test_average_contribution_with_partial_neighbor_data` — some neighbors lack last_contribution
7. `test_average_contribution_shows_own_action_before_average` — own event formatted first
8. `test_no_visible_neighbors_with_contributions_shows_only_own_action` — fallback path

**Group D: Structured context gaps (2 tests)**
9. `test_structured_context_handles_non_consecutive_rounds` — gaps in round numbers
10. `test_structured_context_with_missing_my_event_skips_own_action` — no crash

---

## Module 5: `core/experiment/runner.py` — 85% (479 stmts)

### Why It Matters

The runner orchestrates round execution. Uncovered paths include PGG phase transitions, string-to-int conversion for LLM outputs, visibility mode routing, and empty LLM response handling. These are the **crash-on-edge-case** paths that kill long-running experiments.

### What Exists

`tests/core/experiment/test_runner.py` — covers basic round execution, action replay, and history events.

### What to Write

**File:** `tests/core/experiment/test_runner_edge_cases.py`

#### Test Cases

**Group A: LLM response edge cases (3 tests)**
1. `test_empty_llm_response_returns_skip_action` — empty string → ActionResult with skip=True
2. `test_none_llm_response_returns_skip_action` — None from client
3. `test_action_amount_as_string_converted_to_int` — LLM returns "5" instead of 5

**Group B: PGG phase transitions (3 tests)**
4. `test_pgg_phase_advances_after_allocate_round` — allocate → deduct toggle
5. `test_deduction_budget_reset_when_entering_deduct_phase` — budgets refilled
6. `test_deduction_budget_not_reset_when_not_deduct_phase` — no reset in allocate

**Group C: Visibility mode routing (2 tests)**
7. `test_run_single_round_delegates_to_sequential_mode` — round_visibility="sequential"
8. `test_run_single_round_delegates_to_random_mode` — round_visibility="random"

**Group D: Circuit breaker (1 test)**
9. `test_circuit_breaker_skips_agent_after_consecutive_failures` — 3+ failures → agent skipped

**Group E: Contribution storage in different modes (3 tests)**
10. `test_sequential_mode_stores_last_contribution` — stored for average display
11. `test_random_mode_stores_last_contribution_with_string_amount` — string→int conversion
12. `test_paired_mode_stores_last_contribution_per_pair` — pairing_fn used

**Group F: Host messages and feedback (2 tests)**
13. `test_host_message_prepended_to_agent_context` — pending_host_messages injected
14. `test_environment_feedback_injected_into_context` — feedback text appears

**Group G: Legacy compatibility (2 tests)**
15. `test_legacy_payoff_config_without_payoff_config_dict` — old-style fields used
16. `test_context_summary_used_when_no_round_history` — shared context fallback

---

## Module 6: `core/experiment/action_handler.py` — 69% (80 stmts)

### Why It Matters

The generic action dispatch handles declarative effects on agent resources and extensions. Uncovered branches include subtract/set operations and template variable substitution. Bugs here mean **wrong resource calculations**.

### What Exists

`tests/core/experiment/test_pgg_handlers.py` — tests for handle_reduce. No tests for the generic dispatch logic.

### What to Write

**File:** `tests/core/experiment/test_action_handler_dispatch.py`

#### Test Cases

1. `test_unknown_requirement_returns_true` — unsupported requirement type allows action
2. `test_static_value_effect_applied_when_not_in_params` — literal value used
3. `test_effect_application_when_agent_missing_from_state` — no crash, early return
4. `test_resource_subtract_operation` — deduct from existing resource
5. `test_resource_add_operation_creates_field` — new resource key created
6. `test_resource_set_operation_replaces_value` — overwrite existing
7. `test_extension_effect_with_template_variable` — `{pool_name}` resolved from params
8. `test_extension_effect_creates_nested_structure` — extensions dict auto-created
9. `test_extension_add_initializes_to_zero_before_adding` — missing sub-field defaults to 0
10. `test_extension_set_creates_full_path` — deep nested set

---

## Module 7: `core/experiment/kernel.py` — 84% (125 stmts)

### Why It Matters

The kernel manages action registration and schema generation. Uncovered paths handle unknown actions and parameter type conversion for schemas. Low bug severity but straightforward to test.

### What Exists

`tests/core/experiment/test_kernel.py` — covers built-in action registration, parameter modes, execution, and basic schema generation.

### What to Write

**File:** `tests/core/experiment/test_kernel_schemas.py`

#### Test Cases

1. `test_get_action_returns_none_for_unregistered_action` — unknown name
2. `test_needs_parameters_returns_false_for_unknown_action` — action_class is None
3. `test_parameter_spec_to_schema_number_type` — maps to integer/number
4. `test_parameter_spec_to_schema_text_type` — maps to string
5. `test_parameter_spec_to_schema_agent_type` — maps to string with agent description
6. `test_parameter_spec_to_schema_enum_type` — includes enum values in schema
7. `test_parameter_spec_to_schema_with_options` — adds enum + enhanced description
8. `test_get_action_schemas_excludes_empty_parameter_actions` — no-params actions filtered
9. `test_get_action_schemas_includes_mode_for_each_action` — json vs plain_text

---

## Module 8: `core/experiment/state.py` — 70% (52 stmts)

### Why It Matters

ExperimentState is the shared mutable state for experiment rounds. Uncovered methods handle auto-creation of missing agents and pool operations. Simple CRUD but worth testing for correctness.

### What Exists

Basic tests in experiment test files covering initialization, serialization, position, and resources.

### What to Write

**File:** `tests/core/experiment/test_state_operations.py`

#### Test Cases

1. `test_update_agent_position_creates_agent_if_missing` — auto-creation
2. `test_update_agent_score_creates_agent_if_missing` — auto-creation with score delta
3. `test_update_agent_score_adds_negative_delta` — score decreases
4. `test_update_agent_resource_creates_agent_if_missing` — auto-creation
5. `test_update_agent_resource_sets_new_resource_type` — creates new key
6. `test_add_to_pool_initializes_pools_extension` — creates extensions["pools"]
7. `test_add_to_pool_initializes_individual_pool` — creates pool[name]
8. `test_add_to_pool_adds_to_existing_amount` — accumulation
9. `test_get_pool_returns_zero_for_missing_pool` — safe default
10. `test_get_pool_returns_zero_when_pools_extension_missing` — safe default
11. `test_get_pool_returns_current_amount` — existing value

---

## Module 9: `core/scenes/policy_cascade/distortion.py` — 51% (288 stmts)

### Why It Matters

Distortion algorithms modify how agents perceive policy text based on their tier, alignment, and distortion strength. This is active research code with complex branching. Bugs here mean **distorted results that look valid**.

### What Exists

`tests/integration/test_policy_cascade_multiround.py` — covers tier progression, basic distortion detection, and message distortion at high strength.

### What to Write

**File:** `tests/core/scenes/policy_cascade/test_distortion.py`

#### Test Cases

**Group A: Helper functions (5 tests)**
1. `test_clamp01_below_zero_returns_zero` — -0.5 → 0.0
2. `test_clamp01_above_one_returns_one` — 1.5 → 1.0
3. `test_keyword_score_zero_for_empty_text` — no text → 0.0
4. `test_keyword_score_zero_when_no_keywords_match` — irrelevant text → 0.0
5. `test_keyword_score_returns_1_when_all_match` — all keywords present → 1.0

**Group B: Agent and policy profiling (4 tests)**
6. `test_agent_signal_text_includes_role_and_profile` — contains expected strings
7. `test_agent_signal_profile_returns_scores_for_all_markers` — all marker types scored
8. `test_policy_signal_profile_extracts_from_source_policy` — correct state field
9. `test_policy_signal_profile_modifies_by_condition` — condition values affect scores

**Group C: Block tendency (3 tests)**
10. `test_block_tendency_higher_for_low_tier_than_high` — tier ordering
11. `test_block_tendency_increases_with_distortion_strength` — monotonic
12. `test_block_tendency_includes_deterministic_seed` — same inputs → same result

**Group D: Policy line parsing and classification (4 tests)**
13. `test_split_policy_line_on_colon` — "Goal: Reduce emissions" → ("Goal", "Reduce emissions")
14. `test_split_policy_line_on_chinese_colon` — "目标：减排" → ("目标", "减排")
15. `test_split_policy_line_no_colon_returns_empty_header` — full line as body
16. `test_line_kind_classifies_by_header_markers` — title/goal/execution/general categories

**Group E: Policy softening (3 tests)**
17. `test_soften_body_replaces_mandatory_words_at_moderate_strength` — "必须" → "优先"
18. `test_soften_body_replaces_time_expressions_at_high_strength` — strength >= 0.65
19. `test_soften_body_returns_original_at_low_strength` — strength < 0.35, no changes

**Group F: Line rewriting by kind and tier (4 tests)**
20. `test_rewrite_title_line_unchanged` — title lines never modified
21. `test_rewrite_meta_line_unchanged` — meta/invariant lines preserved
22. `test_rewrite_goal_line_prefixed_at_moderate_strength` — conditional prefix added
23. `test_rewrite_execution_line_simplified_at_high_strength` — weakens requirements

**Group G: Line priority and filtering (3 tests)**
24. `test_line_priority_varies_by_tier` — different ordering for different tiers
25. `test_must_keep_true_for_title_and_meta` — always preserved
26. `test_must_keep_varies_by_strength` — fewer kept at higher strength

**Group H: Main distortion function (3 tests)**
27. `test_distort_message_returns_original_at_zero_strength` — no-op
28. `test_distort_message_returns_original_for_empty_message` — no-op
29. `test_distort_message_adds_prefix_and_constraint_label` — structure of output

---

## Module 10: `core/contagion/statistics.py` — 68% (34 stmts)

### Why It Matters

Calculates aggregate statistics from contagion simulation state. Wrong statistics = wrong research conclusions.

### What to Write

**File:** `tests/core/contagion/test_contagion_statistics.py`

#### Test Cases

1. `test_compute_statistics_counts_each_state_correctly` — S=3, E=1, I=2, R=1
2. `test_compute_statistics_handles_empty_agent_list` — all zeros
3. `test_compute_statistics_handles_all_susceptible` — no transitions yet

---

## Module 11: `core/contagion/actions.py` — 82% (11 stmts)

### Why It Matters

MoveAdjacentAction and SpeakToAction definitions for contagion. No existing tests.

### What to Write

**File:** `tests/core/contagion/test_contagion_actions.py`

#### Test Cases

1. `test_move_adjacent_action_has_correct_name` — NAME attribute
2. `test_speak_to_action_has_correct_name` — NAME attribute
3. `test_direction_deltas_contain_all_eight_directions` — N, NE, E, SE, S, SW, W, NW

---

## Module 12: Frontend i18n — Missing `auth.login.*` Keys (0% coverage)

### Why It Matters

The `LoginPage.tsx` uses 11 `t("auth.login.*")` keys, but **none of them exist** in either `frontend/locales/en.json` or `frontend/locales/zh.json`. When `t()` can't find a key, it returns the raw key string — so users currently see literal strings like `"auth.login.welcome"` instead of actual text. The register page keys exist and work correctly; only the login page is completely broken.

### What Exists

- `auth.register.*` — 17 keys, fully present in both locales
- `auth.layout.*` — 3 keys (EXHIBITS, JOURNALS, INDEX), present in both locales
- `auth.login.*` — **0 keys** in either locale file

### Missing Keys

These keys are used in `LoginPage.tsx` but have no locale entries:

| Key | Used At | Purpose |
|-----|---------|---------|
| `auth.login.badge` | Hero badge section | Badge text above welcome |
| `auth.login.welcome` | Page title `<h2>` | Welcome heading |
| `auth.login.subtitle` | Subtitle `<p>` | Page subtitle |
| `auth.login.email` | Email field label | "Email" |
| `auth.login.emailPlaceholder` | Email input placeholder | "Enter your email" |
| `auth.login.password` | Password field label | "Password" |
| `auth.login.passwordPlaceholder` | Password input placeholder | "Enter your password" |
| `auth.login.invalid` | Error message on failed login | "Invalid email or password" |
| `auth.login.noAccount` | Footer text | "Don't have an account?" |
| `auth.login.create` | Footer link | "Create one" |
| `auth.login.signin` | Submit button | "Sign in" |

### What to Write

**File:** `frontend/locales/en.json` and `frontend/locales/zh.json`

**Task:** Add the `"login"` section under `"auth"` with all 11 keys.

**English values:**
```json
"login": {
  "badge": "Social Systems Laboratory",
  "welcome": "Welcome back",
  "subtitle": "Sign in to continue to your simulations",
  "email": "Email",
  "emailPlaceholder": "you@example.com",
  "password": "Password",
  "passwordPlaceholder": "Enter your password",
  "invalid": "Invalid email or password. Please try again.",
  "noAccount": "Don't have an account?",
  "create": "Create one",
  "signin": "Sign in"
}
```

**Chinese values:**
```json
"login": {
  "badge": "Social Systems Laboratory",
  "welcome": "欢迎回来",
  "subtitle": "登录以继续您的模拟实验",
  "email": "邮箱",
  "emailPlaceholder": "you@example.com",
  "password": "密码",
  "passwordPlaceholder": "输入您的密码",
  "invalid": "邮箱或密码无效，请重试。",
  "noAccount": "还没有账户？",
  "create": "创建一个",
  "signin": "登录"
}
```

**File:** `tests/test_i18n_register_page.py` — add a companion `tests/test_i18n_login_page.py`

**Test cases:**
1. `test_login_page_keys_in_en` — every `t("auth.login.*")` key exists in `en.json`
2. `test_login_page_keys_in_zh` — every `t("auth.login.*")` key exists in `zh.json`
3. `test_login_page_uses_all_expected_keys` — no extra or missing keys vs expected set

### Backend i18n Note

The key `welcome.user` is referenced only in `src/fos/i18n.py` docstring examples (line 118), not in actual code. No backend action needed.

---

## Execution Order

Write tests in this order — highest impact first:

1. **Frontend auth.login i18n** (Module 12) — users see raw keys instead of text. Fix the locale files first.
2. **SimTree** (Module 1) — most dangerous untested code
3. **Contagion scene** (Module 2) — wrong infection rates
4. **Context builder** (Module 4) — agents see wrong info
5. **Experiment scene** (Module 3) — wrong payoffs
6. **Runner** (Module 5) — experiment crashes
7. **Action handler** (Module 6) — wrong resource math
8. **State** (Module 8) — simple, quick wins
9. **Kernel** (Module 7) — schema generation
10. **Distortion** (Module 9) — research-specific
11. **Contagion statistics + actions** (Modules 10-11) — small, easy

---

## Estimated Impact

| Module | New Tests | Expected Coverage | Bug Class Prevented |
|--------|-----------|-------------------|---------------------|
| **Frontend auth.login i18n** | **3 + locale fix** | **0% → 100%** | **Users see raw keys instead of text** |
| simtree.py | ~59 | 18% → 75%+ | Shared state between branches |
| contagion/scene.py | ~23 | 63% → 90%+ | Wrong infection rates |
| experiment/scene.py | ~20 | 74% → 88%+ | Wrong payoff calculations |
| context_builder.py | ~10 | 81% → 95%+ | Agents see wrong context |
| runner.py | ~16 | 85% → 93%+ | Experiment crashes mid-run |
| action_handler.py | ~10 | 69% → 90%+ | Wrong resource math |
| state.py | ~11 | 70% → 95%+ | State corruption |
| kernel.py | ~9 | 84% → 95%+ | Schema generation errors |
| distortion.py | ~29 | 51% → 85%+ | Wrong distortion output |
| contagion statistics | ~3 | 68% → 95%+ | Wrong aggregate stats |
| contagion actions | ~3 | 82% → 100% | Action definition errors |
| **Total** | **~196** | **53% → ~65%** | |

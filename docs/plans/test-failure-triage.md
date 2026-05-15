# Test Failure Triage

Date: 2026-05-15
Total failing: 34
Total errors: 2

---

## Summary table

| Category | Count | Action needed |
|----------|-------|---------------|
| Real bugs | 3 | Fix before launch |
| Stale tests | 17 | Delete or update |
| Infrastructure | 12 | Setup/config issue |
| Errors (fixture) | 2 | Move to dedicated test run |

---

## Real Bugs

### test_visibility_filtering (tests/unit/test_context_builder_visibility.py)
**Error:** `AssertionError: assert 'Agent 3' not in 'Round 1: I ...ent 3 green.'`
**What it means:** The neighborhood visibility filter leaks events from non-neighbor agents. Agent 1 sees Agent 3's action despite Agent 3 not being in their neighborhood.
**Severity:** High — information model isolation is broken, agents see data they shouldn't. Affects experiment validity.

### test_coordination_game_runs_with_neighbor_visibility (tests/unit/experiment/test_experiment_scene_state.py)
**Error:** `AssertionError: assert ['', ''] == ['red', 'blue']` — controller logs `Failed to parse JSON from Node1: Expecting value: line 1 column 1 (char 0)`
**What it means:** The StubLLM `chat()` return value is not reaching the controller correctly. The controller receives an empty string instead of the JSON the stub produces. Likely a mismatch between how `ExperimentScene.run_round()` calls the LLM vs what the stub provides (method signature, response wrapping, or the scene extracts `.content` from a response object while the stub returns a bare string).
**Severity:** High — the mock/LLM interface contract is broken, blocking all experiment scene tests.

### test_custom_contribute_action_writes_state_and_survives_serialize (tests/unit/experiment/test_experiment_scene_state.py)
**Error:** `assert 20 == 13` — agent tokens stay at 20 instead of being reduced to 13 (20 - 7)
**What it means:** The followup response `{"amount": 7, "pool": "main"}` is never parsed/processed. Same root cause as above — the LLM response doesn't reach the controller as expected, so the contribute action's followup prompt never produces a valid result.
**Severity:** High — contribute/pool mechanics are broken in experiments.

---

## Stale Tests

### test_all_scope_agents_see_everyone (tests/integration/test_experiment_knowledge_scope.py)
**Error:** `RuntimeError: There is no current event loop in thread 'MainThread'.`
**Why stale:** Uses deprecated `asyncio.get_event_loop().run_until_complete()` which was removed in Python 3.12+. Tests need to use `asyncio.run()` or `pytest-asyncio`.
**Action:** Update to `asyncio.run()` or mark with `@pytest.mark.asyncio`.

### test_context_budget_enforced_in_prompt (tests/integration/test_experiment_knowledge_scope.py)
**Error:** Same `RuntimeError: There is no current event loop` as above.
**Why stale:** Same deprecated asyncio pattern.
**Action:** Update to `asyncio.run()` or mark with `@pytest.mark.asyncio`.

### test_pair_scope_no_cross_pair_knowledge_leak (tests/integration/test_experiment_knowledge_scope.py)
**Error:** Same `RuntimeError: There is no current event loop` as above.
**Why stale:** Same deprecated asyncio pattern.
**Action:** Update to `asyncio.run()` or mark with `@pytest.mark.asyncio`.

### test_self_scope_agents_see_only_own_history (tests/integration/test_experiment_knowledge_scope.py)
**Error:** Same `RuntimeError: There is no current event loop` as above.
**Why stale:** Same deprecated asyncio pattern.
**Action:** Update to `asyncio.run()` or mark with `@pytest.mark.asyncio`.

### test_llm_distribution (tests/integration/test_llm_distribution.py)
**Error:** `IndexError: list index out of range` on `scene.agents[0]`
**Why stale:** Test creates `ExperimentScene(config)` but never calls `scene.initialize()`. Agents list is empty because initialization was moved to a separate method.
**Action:** Update test to call `scene.initialize(mock_client)` before accessing agents.

### test_llm_distribution_runtime (tests/integration/test_llm_distribution_smoke.py)
**Error:** `TypeError: ExperimentScene.run_round() missing 1 required positional argument: 'event_emitter'`
**Why stale:** `run_round()` signature changed to require an `event_emitter` callback parameter.
**Action:** Update test to pass an event emitter: `await scene.run_round(lambda e, d: None)`.

### test_llm_client_selection (tests/integration/test_llm_distribution_smoke.py)
**Error:** `TypeError: __init__() should return None, not 'MagicMock'`
**Why stale:** `scene.initialize(mock_client)` creates real `AgentLLMClient` objects internally for `dialect="mock"`, which clashes with the test's attempt to inject a MagicMock.
**Action:** Update to use a proper mock client or configure agents without `dialect="mock"`.

### test_fix_1_visibility_filtering (tests/manual/test_coordination_manual.py)
**Error:** `ValueError: scope_type must be one of {'pair', 'role_based', 'self', 'all', 'neighborhood'}, got neighbor`
**Why stale:** Test uses `scope_type="neighbor"` but the valid value was renamed to `"neighborhood"`.
**Action:** Update `scope_type` from `"neighbor"` to `"neighborhood"`.

### test_fix_2_no_score_display (tests/manual/test_coordination_manual.py)
**Error:** Same `ValueError: ...got neighbor` as above.
**Why stale:** Same scope_type rename.
**Action:** Update `scope_type` from `"neighbor"` to `"neighborhood"`.

### test_open_discussion_basic (tests/smoke_tests/test_discussion.py)
**Error:** `AttributeError: 'ExperimentKernel' object has no attribute 'register_action'`
**Why stale:** `ExperimentKernel.register_action()` method was removed/renamed. The kernel API changed.
**Action:** Update to use current kernel API for registering actions.

### test_open_discussion_no_scores (tests/smoke_tests/test_discussion.py)
**Error:** Same `AttributeError: 'ExperimentKernel' object has no attribute 'register_action'` as above.
**Why stale:** Same kernel API change.
**Action:** Update to use current kernel API.

### test_echo_chamber_neighbor_visibility (tests/smoke_tests/test_sociology.py)
**Error:** `ValueError: scope_type must be one of {...'neighborhood'...}, got neighbor`
**Why stale:** Same scope_type rename.
**Action:** Update `scope_type` from `"neighbor"` to `"neighborhood"`.

### test_en_prompt_values_have_no_chinese (tests/test_i18n_llm_prompts.py)
**Error:** `AssertionError: 1 en.json prompt value(s) contain Chinese characters` — `prompts.policy_cascade.status.thread_ban_generic` contains "继续"
**Why stale:** i18n enforcement test found a real violation — English locale file contains Chinese. The test is correct; the data is stale.
**Action:** Fix the en.json value to remove the Chinese character "继续" → use English equivalent like "proceed".

### test_zh_prompt_values_have_no_english_sentences (tests/test_i18n_llm_prompts.py)
**Error:** `AssertionError: 35 zh.json prompt value(s) contain English text` — many `policy_cascade` and `actions.*.instruction` values have mixed English/Chinese.
**Why stale:** Many zh.json prompt values still contain English sentences from templates that were copied but not fully translated.
**Action:** Translate the 35 identified values to proper Chinese, or mark template-format strings as exempt.

### test_prompt_t_calls_pass_locale (tests/test_i18n_llm_prompts.py)
**Error:** `AssertionError: 21 T('prompts.*') call(s) missing locale= argument` in `base_actions.py` and `policy_feedback_actions.py`
**Why stale:** Action classes use `T("key")` at class attribute level without passing `locale=`. The i18n migration is incomplete.
**Action:** Add `locale=` parameter to all 21 identified `T()` calls.

### test_no_hardcoded_english_in_prompt_builders (tests/test_i18n_llm_prompts.py)
**Error:** `AssertionError: 4 hardcoded English string(s) returned from prompt builder code` in `kernel.py` and `council_experiment.py`
**Why stale:** Four methods return hardcoded English strings instead of using `T()`.
**Action:** Move strings to locale JSON files and use `T()`.

---

## Infrastructure Issues

### test_process_response_does_not_record_to_context_manager (tests/unit/test_controller_no_recording.py)
**Error:** `RuntimeError: There is no current event loop in thread 'MainThread'.`
**What is needed:** Tests use deprecated `asyncio.get_event_loop().run_until_complete()`. Need `asyncio.run()` or `pytest-asyncio`.

### test_process_response_with_followup_no_recording (tests/unit/test_controller_no_recording.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_process_response_with_followup_collects_contribute_amount (tests/unit/test_controller_no_recording.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_followup_prompt_reuses_main_prompt_context (tests/unit/test_controller_no_recording.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_runner_without_information_model_still_works (tests/unit/test_runner_information_model.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_runner_records_events_with_all_scope_simultaneous (tests/unit/test_runner_information_model.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_runner_pair_scope_no_knowledge_leak_simultaneous (tests/unit/test_runner_information_model.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_runner_sequential_records_immediately (tests/unit/test_runner_information_model.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_run_round_completes (tests/unit/test_contagion_pipeline_a.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_seir_states_change (tests/unit/test_contagion_pipeline_a.py)
**Error:** Same `RuntimeError: There is no current event loop`.
**What is needed:** Same asyncio fix.

### test_average_contribution_e2e (tests/manual/test_average_contribution_fix.py)
**Error:** `async def functions are not natively supported. You need to install pytest-asyncio or similar.`
**What is needed:** Install `pytest-asyncio` and add `@pytest.mark.asyncio` decorator.

### test_coordination_game_replays_feedback_into_next_round_prompt (tests/unit/experiment/test_experiment_scene_state.py)
**Error:** `IndexError: list index out of range` — `llm.prompts[2]` fails because only 0-1 prompts were recorded.
**What is needed:** Same LLM mock interface mismatch as the real bugs above — the stub's `chat()` response doesn't reach the controller. Once the mock interface is fixed, this test should work or need assertion adjustment.

---

## ERROR tests

### test_pattern (tests/llm_prompt_testing/run_pattern_test.py)
**Error:** `fixture 'pattern' not found`
**What it is:** This test requires a custom pytest fixture (`pattern`) that is not available when running the full test suite. It's designed to be run with a specific conftest.py or CLI parameter that provides the pattern fixture. Not a bug — it's a parameterized LLM prompt test runner.

### test_action (tests/llm_prompt_testing/test_all_platform_actions.py)
**Error:** `fixture 'client' not found` (and also `model_config`, `action_name`, `action_data`, `format_type`, `run_index`, `agent`)
**What it is:** Same situation — requires custom fixtures from a conftest.py that injects an Ollama client and test parameters. This is an LLM prompt testing harness meant to be run in isolation with specific CLI arguments.

---

## Recommended fix order

### Priority 1 — Real bugs (fix before launch)

1. **test_visibility_filtering** — Neighborhood information model leaks events. Core experiment integrity issue. Fix `build_structured_context()` to properly filter by observed_by.
2. **StubLLM mock interface mismatch** (affects 3 tests in `test_experiment_scene_state.py`) — Determine what `ExperimentScene.run_round()` actually passes to the LLM client and how it extracts the response. Update stubs or fix the scene→controller handoff. This unblocks: `test_coordination_game_runs_with_neighbor_visibility`, `test_custom_contribute_action_writes_state_and_survives_serialize`, and `test_coordination_game_replays_feedback_into_next_round_prompt`.

### Priority 2 — Stale tests (quick fixes, bulk update)

3. **Asyncio deprecation** (12 tests) — Replace `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()` across 6 files. Alternatively, install `pytest-asyncio` and use `@pytest.mark.asyncio`. This is a single mechanical fix pattern.
4. **scope_type "neighbor" → "neighborhood"** (3 tests) — One-line fix in each of 3 test files.
5. **ExperimentKernel.register_action removed** (2 tests) — Update to current kernel API.
6. **test_llm_distribution** — Add `scene.initialize()` call.
7. **test_llm_distribution_smoke tests** (2 tests) — Update for new `run_round()` signature and mock client handling.

### Priority 3 — i18n cleanup (can ship without)

8. **i18n test failures** (4 tests in `test_i18n_llm_prompts.py`, 2 in `test_i18n_backend.py`) — These are enforcement tests catching incomplete i18n migration. Fix the 35 mixed-language zh.json values, 1 Chinese string in en.json, 21 missing `locale=` args, and 4 hardcoded English strings. Non-blocking for launch but important for production quality.

### Priority 4 — Not actionable in this context

9. **LLM prompt testing ERRORs** (2 tests) — Move to a separate test run configuration with appropriate conftest/fixtures. These are integration tests requiring a running Ollama instance.

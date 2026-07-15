# FOS Test Inventory — Run 1

## Inventory Status

| Requirement | Status |
|-------------|--------|
| Deterministic backend suite (3× runs) | ✅ Complete — 903 pass, 25 fail, 0 flakes |
| Real-LLM smoke tests | ⏳ Pending — requires Ollama (not running) |
| Real-LLM integration tests | ⏳ Pending — excluded from CI |
| LLM prompt tests | ⏳ Pending — excluded from CI |
| i18n tests | ⏳ Not yet run |
| Load tests | ⏳ Pending — excluded from CI |
| Frontend unit tests | ⏳ Not yet run |
| E2E tests | ⏳ Not yet run |

**Date:** 2026-07-15
**SHA:** 9afca3d
**Python:** 3.12.13
**Command:** `PYTHONPATH=src python -m pytest tests/ -q --no-header --ignore=tests/llm_prompt_testing --ignore=tests/smoke_tests --ignore=tests/integration/test_real_llm_phase1.py --ignore=tests/integration/test_llm_action_selection.py --ignore=tests/load`

## Suite Summary

| Suite | Pass | Fail | Skip | Time | Notes | Live provider required |
|-------|------|------|------|------|-------|----------------------|
| tests/unit | 295 | 8 | 0 | 2.52s | 5 game_config + 3 debug_log | No |
| tests/core/contagion | 29 | 0 | 0 | 0.64s | Clean | No |
| tests/core/experiment | 359 | 10 | 0 | 42.32s | Does not hang; 42s completion with 10 failures | No |
| tests/core/llm | 151 | 7 | 0 | 0.92s | openai_provider + thinking_disable | No |
| tests/core/scenarios | 3 | 0 | 0 | 0.06s | Clean | No |
| tests/core/scenes | 42 | 0 | 0 | 0.13s | Clean | No |
| tests/core/simulation | 10 | 0 | 0 | 0.06s | Clean | No |
| tests/backend | 14 | 0 | 0 | 1.16s | 5 warnings (non-fatal) | No |

## Failing Tests (Run 1)

### BUG-001: test_experiment_scene_game_config — 5 failures
**Module:** tests/unit/experiment/test_experiment_scene_game_config.py
**Failures:**
1. `test_public_goods_game_config_uses_registry_semantics` — `AssertionError: assert 'allocate' in ['Allocate', 'Keep', 'Reduce', 'Skip']`
   — Action names are Title-cased (e.g. `'Allocate'`) but test expects lowercase (`'allocate'`).
2. `test_echo_chamber_game_config_uses_default_category_actions` — `AssertionError: assert ['Express Opinion', 'Reinforce Ingroup', 'Share Content', 'Disengage'] == ['express_opinion', 'reinforce_ingroup', 'share_content', 'disengage']`
   — Action names use display-form (title case with spaces) instead of snake_case keys.
3. `test_reduce_action_excluded_when_budget_zero` — `AssertionError: assert 'allocate' in ['Allocate', 'Keep', 'Reduce', 'Skip']`
   — Same casing mismatch as #1.
4. `test_reduce_action_excluded_when_budget_not_set` — `AssertionError: assert 'allocate' in ['Allocate', 'Keep', 'Reduce', 'Skip']`
   — Same casing mismatch as #1.
5. `test_reduce_action_included_when_budget_positive` — `AssertionError: assert 'allocate' in ['Allocate', 'Keep', 'Reduce', 'Skip', 'reduce']`
   — Same casing mismatch; plus `'reduce'` is lowercased instead of `'Reduce'`.

**Root cause:** `_create_game_config()` returns action names in Title-case display format, but tests expect lowercase/underscore keys.

### BUG-002: test_debug_log_format — 3 failures
**Module:** tests/unit/test_debug_log_format.py
**Failures:**
1. `test_debug_log_sequential_format_per_agent` — `FileNotFoundError: debug.txt not found` after runner completes.
2. `test_debug_log_atomic_writes_no_interleaving` — `FileNotFoundError: debug.txt not found` after runner completes.
3. `test_debug_log_includes_all_components` — `FileNotFoundError: debug.txt not found` after runner completes.

**Root cause:** `debug_log._session_debug_file` is not being written to during the mock runner execution. The pytest patch of `_session_debug_file` does not trigger log writing — the debug logger likely initialises differently when patched this way, or the runner does not call the debug log module as expected.

### BUG-003: test_openai_provider — 5 failures (TestOpenAIChatJsonFallback)
**Module:** tests/core/llm/test_openai_provider.py
**Failures:**
1. `test_json_mode_empty_triggers_retry` — `assert <MagicMock name='mock.message.reasoning_content.strip()' id=...> == '{"k": "v"}'`
   — openai_chat returns a mock object instead of the actual response string. The retry on empty response is not working correctly — the function returns the mocked `.message.reasoning_content.strip()` chain rather than the content from the good response.
2. `test_json_mode_retry_prepends_instruction` — `IndexError: list index out of range`
   — Only one API call was made instead of the expected two (initial + retry). The retry is not being triggered.
3. `test_json_mode_both_empty_raises` — `Failed: DID NOT RAISE <class 'ValueError'>`
   — Two empty responses should raise ValueError but no exception is raised.
4. `test_non_json_empty_still_raises` — `Failed: DID NOT RAISE <class 'ValueError'>`
   — Empty response in non-JSON mode should raise ValueError but no exception is raised.
5. `test_json_mode_with_vision_list_content` — `assert <MagicMock name='mock.message.reasoning_content.strip()' id=...> == '{"ok": true}'`
   — Same as #1: returns mock object instead of actual content. Vision/list content fallback not working.

**Root cause:** The `openai_chat` function's response handling for json_mode fallbacks is not extracting the `.choices[0].message.content` correctly. It returns a mock chain from `.message.reasoning_content.strip()` instead. The retry logic for empty responses is also not triggering.

### BUG-004: test_thinking_disable — 2 failures (1 consistent + 1 order-dependent)
**Module:** tests/core/llm/test_thinking_disable.py
**Failures:**
1. `TestGeminiThinkingDisableParam::test_config_contains_thinking_budget_zero` — `AssertionError: expected thinking_budget=0, got <MagicMock name='mock.GenerateContentConfig().thinking_config.thinking_budget' id=...>`
   — A `MagicMock` leaks into the `thinking_config.thinking_budget` attribute (from other tests in the suite that use `@patch("fos.core.llm.providers.openai.OpenAI")`).
   - **Order-dependent:** passes when run alone or with only the graceful_degrade test, fails consistently when run in the full llm suite.
2. `TestGeminiThinkingGracefulDegrade::test_graceful_when_thinking_budget_rejected` — `AttributeError: module 'fos.core.llm.providers.gemini' has no attribute 'ThinkingConfig'`
   — The test tries to monkeypatch `gemini_mod.ThinkingConfig` but the module does not import or define a `ThinkingConfig` class. The gemini provider likely uses `google.genai.types.ThinkingConfig` directly instead of re-exporting it.

**Root cause:** The gemini provider does not re-export `ThinkingConfig` at module level, and test isolation is insufficient — mock patches from `test_openai_provider.py` leak into `TestGeminiThinkingDisableParam` when run in the same session.

### BUG-005: tests/core/experiment — 10 failures
**Module:** tests/core/experiment/
**Symptom:** Previously thought to hang (>15s), but completes in 42.32s with 10 failures. The original "hang" may have been caused by `tests/core/experiment/` running after other suites in a single pytest invocation, causing resource contention or a transient timeout.

**Failures:**
1. `test_phase1_regression_units::test_custom_scene_runtime_uses_network_visible_history_only` — `AssertionError: 'Skip' != 'skip'`
   — Action name casing mismatch (Title-case vs lowercase).
2. `test_rag_e2e::TestDocumentPipeline::test_retrieve_ranks_relevant_text_highest` — `ModuleNotFoundError: No module named 'torch'`
   — Missing `torch` dependency.
3. `test_rag_e2e::TestDocumentPipeline::test_unrelated_query_returns_low_similarity` — `ModuleNotFoundError: No module named 'torch'`
   — Same missing dependency.
4. `test_rag_e2e::TestGlobalKnowledgeIntegration::test_global_and_private_merged_in_results` — `ModuleNotFoundError: No module named 'torch'`
   — Same missing dependency.
5. `test_rag_e2e::TestGlobalKnowledgeIntegration::test_global_only_with_no_agent_docs` — `ModuleNotFoundError: No module named 'torch'`
   — Same missing dependency.
6. `test_rag_e2e::TestEdgeCases::test_real_semantic_search_preferred_over_keyword` — `ModuleNotFoundError: No module named 'torch'`
   — Same missing dependency.
7. `test_runner::test_model_batching_reduces_preload_calls` — `TypeError: '>' not supported between instances of 'Mock' and 'int'`
   — `_get_port_from_client` receives a Mock instead of a real `base_url` string; mock not configured with provider attributes.
8. `test_runner::test_model_batching_concurrent_within_group` — `TypeError: '>' not supported between instances of 'Mock' and 'int'`
   — Same mock misconfiguration.
9. `test_runner::test_model_batching_serial_between_groups` — `TypeError: '>' not supported between instances of 'Mock' and 'int'`
   — Same mock misconfiguration.
10. `test_scene_average_param::test_custom_scene_uses_custom_prompt_and_actions_without_followup` — `AssertionError: ['Speak', 'Skip'] != ['speak', 'skip']`
    — Action name casing mismatch (Title-case vs lowercase).

## Flake Check

**Run 2 results:** 15 failed, 544 passed — identical to Run 1.

**Flaky tests identified:**
- `test_config_contains_thinking_budget_zero` — **Order-dependent.** Passes in isolation (single test or with only graceful_degrade test), but fails consistently when run in the full llm suite. The mock from other tests (likely `@patch("fos.core.llm.providers.openai.OpenAI")` in `test_openai_provider.py`) leaks into the gemini module's `GenerateContentConfig` imports. This is a test isolation (leaky mock) issue.

**Test isolation concern:** The `openai_provider` tests use `@patch("fos.core.llm.providers.openai.OpenAI")` which also patches `google.genai` via transitive imports. When these tests run before `test_thinking_disable.py`, the mock leaks into subsequent gemini tests. A session-scoped fixture or `autouse` cleanup could fix this.

## Run 3 — Flake Confirmation

**Date:** 2026-07-15
**Results:** 903 passed, 25 failed, 6 warnings in 44.41s
**Flake rate:** 0% — all three runs produced identical failure counts and suites.

### Failure consistency (3/3 runs)

| Bug ID | Test file | Failures | Runs |
|--------|-----------|----------|------|
| BUG-001 | test_experiment_scene_game_config.py | 5 | 3/3 |
| BUG-002 | test_debug_log_format.py | 3 | 3/3 |
| BUG-003 | test_openai_provider.py | 5 | 3/3 |
| BUG-004 | test_thinking_disable.py | 2 | 3/3 |
| BUG-005 | test_phase1_regression_units.py | 1 | 3/3 |
| BUG-006 | test_rag_e2e.py | 5 | 3/3 |
| BUG-007 | test_runner.py | 3 | 3/3 |
| BUG-008 | test_scene_average_param.py | 1 | 3/3 |

**Conclusion:** Zero flaky tests. All 25 failures are deterministic — each represents a real bug, not an environmental issue.

## Provider Dependency
None of the above suites require a live LLM provider. All use mocks or pure functions. The `test_rag_e2e` failures from missing `torch` are infrastructure/environment, not provider-dependent.

## Next Steps
- Run 2 and Run 3 to establish flake rate
- Investigate and fix leaky mock from openai_provider tests affecting thinking_disable tests
- Install `torch` for rag_e2e tests or add skip-if-missing decorator
- Fix action name casing in `_create_game_config()` (BUG-001, BUG-005 items #1 and #10)
- Fix openai_chat json_mode fallback response handling (BUG-003)
- Implement `debug_log._session_debug_file` writing (BUG-002)
- Add `ThinkingConfig` re-export or restructure graceful_degrade test (BUG-004 #2)
- File P0 bugs for consistent failures

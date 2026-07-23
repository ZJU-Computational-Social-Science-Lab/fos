# FOS Bug Log

| ID | Date | Sev | Demo-path? | Module | Summary | Status | Regression test | Fixed in |
|----|------|-----|------------|--------|---------|--------|-----------------|----------|
| BUG-001 | 2026-07-15 | P1 | N | Experiment → Game Config | Action names returned in Title-case, tests expect lowercase | FIXED | tests/unit/experiment/test_experiment_scene_game_config.py | d66d017 |
| BUG-002 | 2026-07-15 | P1 | N | Experiment → Debug Log | `_session_debug_file` not written during mock runner execution | FIXED | tests/unit/test_debug_log_format.py | d66d017 |
| BUG-003 | 2026-07-15 | P1 | N | LLM → OpenAI Provider | json_mode fallback returns mock chain instead of message content | FIXED | tests/core/llm/test_openai_provider.py | d66d017 |
| BUG-004 | 2026-07-15 | P2 | N | LLM → Gemini Provider | Mock leak from openai tests + ThinkingConfig not re-exported | FIXED | tests/core/llm/test_thinking_disable.py | d66d017 |
| BUG-005 | 2026-07-15 | P1 | N | Experiment → Regression | Action name casing in test_custom_scene_runtime | FIXED | tests/core/experiment/test_phase1_regression_units.py | d66d017 |
| BUG-006 | 2026-07-15 | P2 | N | Experiment → RAG E2E | `ModuleNotFoundError: torch` — torch not installed | FIXED | tests/core/experiment/test_rag_e2e.py | c8d2852 |
| BUG-007 | 2026-07-15 | P2 | N | Experiment → Runner | Mock object passed to `_get_port_from_client` instead of string | FIXED | tests/core/experiment/test_runner.py | d66d017 |
| BUG-008 | 2026-07-15 | P1 | N | Experiment → Scene Params | Action name casing in test_custom_scene | FIXED | tests/core/experiment/test_scene_average_param.py | d66d017 |

## Severity

- **P0** — blocks a flow, no workaround. Fix before freeze.
- **P1** — works, degraded or confusing.
- **P2** — cosmetic / rare edge.

## Rules
1. **Demo-path column beats severity.** A P1 on slide 3 outranks a P0 in a feature you'll never show.
2. **Every P0 fix ships with a committed regression test.** Non-negotiable — Ziwei's #3 refactor lands while you're presenting, and an uncommitted manual check will not survive it.

## Bug entry template

### BUG-XXX: [Title]
**Date:** 2026-07-XX   **Severity:** P0/P1/P2   **Demo-path:** Y/N
**Found by:** Justin / Ziwei / audience
**Module:** [e.g. AI Scientist → json_repair]
**Steps to reproduce:** [numbered, from a clean demo_seed.db]
**Expected / Actual:**
**Environment:** browser, commit SHA, provider + base URL + model, locale, OS
**Evidence:** [screenshot / HAR / console log / server log]
**Status:** OPEN / IN PROGRESS / FIXED / WONTFIX
**Fixed by:** [commit]   **Regression test:** [path — REQUIRED for P0]
**Verified:** YYYY-MM-DD by [name]

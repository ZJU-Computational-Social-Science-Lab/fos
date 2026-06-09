This note shows how to run the small council pilot with local Ollama models.

# Mock Council Pilot

Use this pilot when you want a cheap stand-in run for the council network
experiment with real local models instead of the synthetic mock provider.

## What It Checks

- Agents only see prior outputs from connected neighbours.
- A short council deliberation round can finish with parseable `speak` or `skip` actions.
- A vote round can finish with parseable `vote_yes`, `vote_no`, or `abstain` actions.
- Current CSV export stays readable for both deliberation and vote outcomes.

## Default Models

If you do not set a model override, the council pilot test uses:

- `ministral-3:3b`
- `granite4:3b`
- `phi4-mini:latest`
- `qwen3:4b-instruct-2507-q4_K_M`

## Environment Variables

- `FOS_TEST_REAL_LLM=1`
  - Turns on real Ollama integration tests.
- `FOS_TEST_COUNCIL_MODELS`
  - Optional comma-separated override for the council pilot model list.
  - Example: `phi4-mini:latest,qwen3:4b-instruct-2507-q4_K_M`
- `FOS_TEST_LLM_BASE_URL`
  - Optional Ollama base URL override.
  - Default: `http://localhost:11434`
- `FOS_TEST_LLM_TEMPERATURE`
  - Optional temperature override.
  - Default: `0.1`
- `FOS_TEST_LLM_MAX_TOKENS`
  - Optional max token override.
  - Default: `256`

## Commands

Run the council pilot tests:

```powershell
$env:FOS_TEST_REAL_LLM="1"
pytest tests/integration/test_real_llm_council_pilot.py -q
```

Run one model only:

```powershell
$env:FOS_TEST_REAL_LLM="1"
$env:FOS_TEST_COUNCIL_MODELS="phi4-mini:latest"
pytest tests/integration/test_real_llm_council_pilot.py -q
```

Run the CSV export check:

```powershell
pytest tests/unit/backend/test_simulation_export_council_csv.py -q
```

## Notes

- If a listed model is not installed locally, its test case skips with an `ollama pull` hint.
- The CSV export check keeps the current schema and reads deliberation text and vote outcomes from `action` and `follow_up`.

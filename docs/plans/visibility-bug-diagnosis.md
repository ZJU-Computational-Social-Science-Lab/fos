# Visibility Bug Diagnosis

## The failing assertion

```
FAILED tests/unit/test_context_builder_visibility.py::test_visibility_filtering

AssertionError: assert 'Agent 3' not in 'Round 1: I red, Agent 2 blue, Agent 3 green.'

  'Agent 3' is contained here:
    Round 1: I red, Agent 2 blue, Agent 3 green.
  ?                               +++++++

tests\unit\test_context_builder_visibility.py:66: AssertionError
```

**Actual output for Agent 1:** `Round 1: I red, Agent 2 blue, Agent 3 green.`  
**Expected:** Agent 3 should not appear in Agent 1's context.  
**Agent that incorrectly sees the wrong event:** Agent 1 sees Agent 3's `green` action.

---

## What the test expects

The test models this directed social network:

```
Agent 2 ←→ Agent 1   (mutual neighbors; each sees the other)
Agent 3  →  Agent 1   (Agent 3 observes Agent 1, but Agent 1 does NOT observe Agent 3)
Agent 2  ✗  Agent 3   (no connection)
```

Therefore:
- **Agent 1** should see Agent 2's action; should NOT see Agent 3's action.
- **Agent 2** should see Agent 1's action; should NOT see Agent 3's action.
- **Agent 3** should see Agent 1's action; should NOT see Agent 2's action.

---

## Where the filter is applied (and works correctly)

File: `src/fos/core/context_builder.py`, line 212

```python
other_events = [e for e in round_events
                if e.agent_name != for_agent and for_agent in e.observed_by]
```

This filter is **correct**. It includes an event in `for_agent`'s context only when `for_agent` is listed in that event's `observed_by`. The logic is sound; the problem lies elsewhere.

---

## Root cause

**The bug is in the test data, not in `build_structured_context`.**

The `observed_by` fields on the test events are inconsistent with the intended social network:

| Event | Current `observed_by` | Should be | Why wrong |
|-------|----------------------|-----------|-----------|
| `event1` (Agent 1 acts) | `["Agent 1", "Agent 2"]` | `["Agent 1", "Agent 2", "Agent 3"]` | Agent 3 observes Agent 1 (3→1 edge), so Agent 3 must be in event1's `observed_by` for `assert "Agent 1" in context3` to pass |
| `event2` (Agent 2 acts) | `["Agent 1", "Agent 2"]` | `["Agent 1", "Agent 2"]` | Correct — Agent 1 and Agent 2 are mutual neighbors |
| `event3` (Agent 3 acts) | `["Agent 1", "Agent 3"]` | `["Agent 3"]` | Agent 1 does NOT observe Agent 3 (no 1→3 edge), so Agent 1 must NOT be in event3's `observed_by` |

**The specific trigger:** `event3.observed_by = ["Agent 1", "Agent 3"]` includes `"Agent 1"`, so the filter at line 212 evaluates `"Agent 1" in ["Agent 1", "Agent 3"]` → `True`, and Agent 3's event is included in Agent 1's context.

Note: the test would also fail at the Agent 3 assertion block (line 88: `assert "Agent 1" in context3`) if it reached it, because `event1.observed_by` does not include `"Agent 3"`. Python stops at the first failure so that second error is hidden.

---

## The fix

Change two `observed_by` fields in the test:

```python
# event1: Agent 1 acts — visible to its neighbors (Agent 2) AND
#          to agents for whom Agent 1 is a neighbor (Agent 3 observes Agent 1)
event1 = RoundEvent(
    agent_name="Agent 1",
    action_name="red",
    parameters={},
    round_num=1,
    summary="Agent 1 chose red",
    observed_by=["Agent 1", "Agent 2", "Agent 3"],   # was ["Agent 1", "Agent 2"]
)

# event3: Agent 3 acts — observed ONLY by Agent 3
#          (Agent 1 does not observe Agent 3 in this network)
event3 = RoundEvent(
    agent_name="Agent 3",
    action_name="green",
    parameters={},
    round_num=1,
    summary="Agent 3 chose green",
    observed_by=["Agent 3"],                          # was ["Agent 1", "Agent 3"]
)
```

No production code changes are needed.

---

## Risk

`build_structured_context` is called via two paths:

1. **`RoundContextManager.get_context_for_agent()`** (`round_context.py:168`):  
   Pre-filters events with `agent_name in e.observed_by` before calling the function. This path is correct; the internal filter at line 212 is redundant but harmless.

2. **Direct calls** (tests and any future callers):  
   The function's docstring says `events` must be pre-filtered by the caller. The secondary filter at line 212 catches unfiltered inputs for `other_events`, but relies on the `observed_by` values being set correctly at write-time.

Fixing the test data touches only the test file. No production code is changed, so there is no regression risk to existing simulation runs.

---

## How to verify the fix

After applying the two `observed_by` changes above:

```bash
PYTHONPATH="src" python -m pytest tests/unit/test_context_builder_visibility.py::test_visibility_filtering -v
```

All three assertion blocks (Agent 1, Agent 2, Agent 3) should pass. Expected contexts:

| Agent | Expected context |
|-------|-----------------|
| Agent 1 | `Round 1: I red, Agent 2 blue.` |
| Agent 2 | `Round 1: Agent 1 red, I blue.` |
| Agent 3 | `Round 1: Agent 1 red, I green.` |

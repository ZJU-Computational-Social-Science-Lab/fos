# StubLLM Mock Interface Diagnosis

## Failing tests

| Test | Error |
|------|-------|
| `test_coordination_game_runs_with_neighbor_visibility` | `AssertionError: assert ['', ''] == ['red', 'blue']` — both actions are empty strings |
| `test_coordination_game_replays_feedback_into_next_round_prompt` | `IndexError: list index out of range` at `llm.prompts[2]` — `StubLLM.chat()` was never called |
| `test_custom_action_parameters_trigger_followup` | `AssertionError: assert '' == 'invest'` — action is empty string |
| `test_custom_contribute_action_writes_state_and_survives_serialize` | `AssertionError: assert 20 == 13` — Alice's tokens unchanged (action never executed) |

All four tests emit the same controller log before failing:
```
ERROR fos.core.experiment.controller:controller.py:153 Failed to parse JSON from <AgentName>: Expecting value: line 1 column 1 (char 0)
```

## StubLLM definition

Every failing test defines a local `StubLLM` with this exact interface:

```python
class StubLLM:
    def __init__(self):
        self.responses = ['{"action": "red"}', '{"action": "blue"}']
        self.index = 0

    def chat(self, messages, json_mode=False):
        response = self.responses[self.index]
        self.index += 1
        return response  # bare JSON string
```

Signature: `chat(self, messages, json_mode=False) -> str`  
Return value: a bare JSON string like `'{"action": "red"}'`

The tests then call `scene.initialize(StubLLM())`.

## Real LLMClient.chat() interface

**File**: `src/fos/core/llm/client.py:227`

```python
def chat(self, messages: List[Dict[str, Any]], json_mode: bool = False) -> str:
```

Signature matches `StubLLM.chat()` — same positional arguments, same return type (bare string).

**For `dialect="mock"`, the body is:**

```python
if self.provider.dialect == "mock":
    def _do():
        openai = _get_openai()
        msgs = openai["normalize_messages_for_openai"](messages, False, validate_media_url)
        return self.client.chat(msgs)  # calls _MockModel.chat(msgs)
    return self._with_timeout_and_retry(_do)
```

`self.client` is a `_MockModel` instance (see `client.py:115`).  
`_MockModel.chat(messages)` returns an XML-formatted string such as:

```
--- Thoughts ---
Say one line this turn.

--- Plan ---
1. Speak once. [CURRENT]

--- Action ---
<Action name="send_message"><message>[1] Hello from Agent.</message></Action>

--- Plan Update ---
no change
```

This is **not JSON**.

## The mismatch

The signature of `StubLLM.chat()` matches `LLMClient.chat()` exactly. **The interface mismatch is not in the signature — it is in the routing.**

`StubLLM.chat()` returns `'{"action": "red"}'` (JSON).  
`LLMClient.chat()` with `dialect="mock"` delegates to `_MockModel.chat()`, which returns XML-format text (not JSON).

**But more critically: `StubLLM` is never called at all.** The tests pass `StubLLM()` to `scene.initialize()`, which stores it in `self.llm_client`, but the runner never uses that field for agents that have explicit `llm_config`.

## Where the empty string comes from

The chain that produces the "Expecting value: line 1 column 1 (char 0)" error:

1. **`scene.initialize()` (`scene.py:104–140`)** sees each agent has `llmConfig: {"dialect": "mock"}`. Because `"mock"` is in `_known_dialects = {"openai", "gemini", "mock", "ollama"}`, it creates a **new real `LLMClient`** object and stores it in `self._agent_llm_clients[agent.name]`. The `StubLLM` passed as `llm_client` is stored in `self.llm_client` (the fallback field) and is never used for these agents.

2. **`runner.get_agent_llm_client(agent)` (`runner.py:114–130`)** finds `agent.name` in `self.agent_llm_clients` and returns the per-agent real `LLMClient`, not the `StubLLM`.

3. **`runner._prompt_agent()` (`runner.py:968–969`)** calls:
   ```python
   raw_response = await asyncio.to_thread(
       agent_llm_client.chat, messages, json_mode=True
   )
   ```
   This calls `LLMClient.chat()` on the real client with `dialect="mock"`, which calls `_MockModel.chat(msgs)`.

4. **`_MockModel.chat()` (`providers/mock.py:37–97`)** finds no system message (the runner only sends a user message), so `sys_text = ""`. It falls through to the `"chat"` scene branch and returns the XML-format string.

5. **`extract_json(xml_text)` (`validation.py:50–95`)** finds no `{` brace in the XML, so it falls back to returning the full XML string as-is.

6. **`controller.process_response()` (`controller.py:124`)** calls `json.loads(xml_text)`. Python's JSON decoder fails immediately at position 0 (the `-` in `---`) and throws `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`.

7. The controller logs the error and returns `ActionResult(success=False, action_name="", ...)`.

**The variable that holds the wrong value** is `raw_response` at `runner.py:968`. It contains the `_MockModel` XML string instead of the `StubLLM`'s JSON string.

## Root cause

In `scene.py:initialize()`, when an agent has `llmConfig: {"dialect": "mock"}`, the code creates a new real `LLMClient` from that config and stores it in `_agent_llm_clients[agent.name]`, **silently discarding the `StubLLM` passed as `llm_client`**. The runner then always uses `_agent_llm_clients` for agents with explicit `llm_config`, so the stub is never called.

## The fix

**Lower-risk option — fix `scene.py:initialize()`:**

Add an early check: if the passed `llm_client` is not an instance of the real `LLMClient` class, it is a duck-typed test stub and should be used directly for all agents, skipping the per-agent routing entirely.

```python
# At the top of the per-agent routing loop in initialize()
from fos.core.llm.client import LLMClient as _RealLLMClient
_is_stub = not isinstance(llm_client, _RealLLMClient)
for agent in self.agents:
    if _is_stub:
        self._agent_llm_clients[agent.name] = llm_client
        continue
    # ... existing routing logic ...
```

This means: if a non-LLMClient object is passed (a test stub), every agent uses it unconditionally. If a real `LLMClient` is passed, per-agent routing via `llm_config.dialect` continues to work as before.

**Alternative — fix the tests (minimal, no prod code change):**

Remove `llmConfig: {"dialect": "mock"}` from agent configs in the four failing tests (or replace with `llmConfig: {}`). Without a recognized dialect, the routing falls through to the `else` branch at `scene.py:144`:

```python
else:
    self._agent_llm_clients[agent.name] = llm_client  # uses StubLLM
```

The StubLLM would then be correctly used. **Risk**: this removes test coverage of the agent-level `llm_config` routing path.

**Recommended**: Fix `scene.py:initialize()` (first option). It is the one correct place to enforce the invariant "a non-LLMClient stub bypasses routing," and it does not require changing test intent.

## Risk

**If fixing `scene.py`:** The only regression risk is if production code ever intentionally passes a real `LLMClient` subclass and wants `dialect`-based routing. Subclasses of `LLMClient` would correctly pass the `isinstance` check, so this is safe for inheritance. The change is contained to `initialize()`.

**If fixing the tests:** The `llmConfig: {"dialect": "mock"}` is present in all four failing tests and appears to be intentional — the intent is to signal "this agent uses mock LLM". Removing it slightly changes what the test exercises, but not the behavior being validated (scene state management).

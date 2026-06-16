# Design: Graceful Handling of Thinking/Reasoning Tokens

**Date**: 2026-06-16
**Status**: Design validated, ready for implementation planning

## Problem

Thinking-capable LLMs (DeepSeek-R1, Qwen3 with thinking enabled, Kimi K2-Thinking, etc.) emit
`<think>...</think>` or similar reasoning tokens in their output. When the FOS platform requests
structured JSON (via `json_mode=True`), these tokens contaminate the response, causing JSON parse
failures and broken experiments.

The platform currently has scattered, inconsistent mitigations (regex stripping in 3 different
places, none of which cover all call sites). There is no API-level attempt to disable thinking
at the source.

## Solution: Two-Layer Defense in Depth

### Layer 1 — API-level disable (prevention)

Before the request leaves the platform, each provider unconditionally passes the appropriate
parameter to disable thinking/reasoning mode. This stops thinking tokens from being generated
in the first place for models that honor the flag.

### Layer 2 — Central output stripping (safety net)

After the response comes back and before any caller sees it, a single unified regex function
strips any thinking tokens that leaked through (some providers/models ignore the disable flag,
or are self-hosted with buggy chat templates).

Both layers run inside `LLMClient.chat()` — the single method through which all chat requests
flow. Every call site (runner, controller, agent, generation, AI scientist) gets both protections
automatically, with zero code changes at call sites.

## Layer 1 Detail: API-Level Disable Per Provider

All parameters are unconditional — always applied, no config toggle, no user-facing option.

### OpenAI-compatible (`providers/openai.py` → `openai_chat`)

```python
kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
```

Passed via `extra_body` so the OpenAI SDK forwards it without validation. Covers
DeepSeek-R1/V4, GLM, Kimi, and any other OpenAI-compatible API that uses the
`thinking` parameter. Non-thinking models silently ignore it.

### Ollama (`providers/ollama.py` → `ollama_chat`)

```python
payload["think"] = False
```

Native Ollama API field. Reliably disables thinking for Qwen3 and similar models
in recent Ollama versions.

### Gemini (`providers/gemini.py` → `gemini_chat`)

```python
config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
```

Wrapped in try/except because Gemini 2.5 Pro rejects `0` — if it fails, log a
warning and proceed without the config (Layer 2 stripping catches anything that
leaks through).

## Layer 2 Detail: Central Output Stripping

### Location

`LLMClient.chat()` calls `strip_thinking_tokens()` on the provider's returned
string before returning to the caller. Single call point, covers all providers.

### Function: `strip_thinking_tokens()` (in `agent/parsing.py`)

Consolidates patterns from existing code (`parsing.py`, `validation.py`,
`generation.py`) and the reference document. Handles:

| Pattern | Example | Models |
|---|---|---|
| XML tags | `<think>...</think>` | Qwen3, DeepSeek |
| Pipe-delimited | `\|think>...\|/think>` | Various GGUF quants |
| Special markers | `<\|thinking\|>...<\|/thinking\|>` | Some GGUF quants |
| Kimi markers | `◁think▷...◁/think▷` | Kimi K2 |
| Bracket markup | `[THINK]...[/THINK]` | Reference doc |
| Markdown sections | `# Thinking\n...` | Edge cases |
| Self-closing | `<think/>` | Edge cases |
| Variant tag names | `<reasoning>`, `<thought>`, `<reflection>`, `<analysis>` | Various |
| Thought-for prefixes | `Thought for 2.3 seconds ` | Some providers |
| Dangling markers | ` /think` at end of line | Edge cases |

All patterns use `re.DOTALL | re.IGNORECASE` for multiline matching.

### Redundant safety nets (kept unchanged)

Existing stripping at call sites remains as defense in depth:
- `experiment/validation.py`: `strip_think_tags()` called inside `extract_json()`
- `experiment/validation.py`: `strip_markdown_fences()` called inside `extract_json()`

The inline regex in `generation.py` is removed (redundant with central stripping).

## Configuration

**No configuration changes.** Everything is unconditional and always-on:
- No new fields on `LLMConfig`
- No environment variables
- No user-facing toggles

Thinking is incompatible with the platform's structured JSON architecture and is
always disabled.

## Tests

### Unit tests (`tests/core/llm/test_thinking_disable.py`)

| Test | What it verifies |
|---|---|
| `test_openai_chat_passes_disable_thinking` | `extra_body={"thinking": {"type": "disabled"}}` in kwargs |
| `test_ollama_chat_passes_think_false` | `"think": False` in payload |
| `test_gemini_chat_passes_thinking_budget_zero` | `ThinkingConfig(thinking_budget=0)` in config |
| `test_gemini_chat_graceful_degrade_on_budget_reject` | Warning logged, no crash when budget=0 rejected |
| `test_strip_thinking_xml_tags` | `<think>content</think>` → `""` |
| `test_strip_thinking_pipe_tags` | `|think>content|/think>` → `""` |
| `test_strip_thinking_special_markers` | `<|thinking|>content<|/thinking|>` → `""` |
| `test_strip_thinking_kimi_markers` | `◁think▷content◁/think▷` → `""` |
| `test_strip_thinking_bracket_markup` | `[THINK]content[/THINK]` → `""` |
| `test_strip_thinking_markdown` | `# Thinking\ncontent` → `""` |
| `test_strip_thinking_self_closing` | `<think/>` → `""` |
| `test_strip_thinking_variant_tags` | `<reasoning>...</reasoning>` → `""` |
| `test_strip_thinking_thought_for_prefix` | `Thought for 2.3s {...}` → `{...}` |
| `test_strip_thinking_valid_json_unchanged` | `{"action":"cooperate"}` → `{"action":"cooperate"}` |
| `test_strip_thinking_nested_in_json` | `<think>x</think>{"a":1}` → `{"a":1}` |
| `test_strip_thinking_empty_input` | `""` → `""` |

### Integration test: Mock (`tests/integration/test_thinking_strip_mock.py`)

Mock provider returns `<think>long chain of thought</think>{"action":"cooperate"}`
→ `chat()` returns only `{"action":"cooperate"}`.

Tests Layer 2 only, no external dependency.

### Integration test: DeepSeek-R1 (`tests/integration/test_thinking_strip_deepseek.py`)

Real API call to DeepSeek-R1 via OpenAI-compatible endpoint. Verifies
the `thinking: {"type": "disabled"}` parameter prevents thinking tokens.

Requires `DEEPSEEK_API_KEY` env var. Skipped if absent.

### Integration test: LM Studio (`tests/integration/test_thinking_strip_lms.py`)

Real call to Qwen3 via LM Studio (lms) local server. Verifies both the
Ollama/OAI-compatible disable param and the regex strip.

Requires LM Studio running with a Qwen3 model loaded. Skipped if unreachable.

## File Change Summary

| File | Change |
|---|---|
| `src/fos/core/llm/providers/openai.py` | `openai_chat()`: add `extra_body={"thinking": {"type": "disabled"}}` to kwargs |
| `src/fos/core/llm/providers/ollama.py` | `ollama_chat()`: add `"think": False` to payload dict |
| `src/fos/core/llm/providers/gemini.py` | `gemini_chat()`: add `thinking_config=ThinkingConfig(thinking_budget=0)` with try/except |
| `src/fos/core/llm/client.py` | `chat()`: call `strip_thinking_tokens()` on result before returning |
| `src/fos/core/agent/parsing.py` | Consolidate `strip_thinking_tokens()` with all patterns |
| `src/fos/core/llm/generation.py` | Remove redundant inline `<think>` regex |
| `tests/core/llm/test_thinking_disable.py` | New: 16 unit tests for disable params + regex stripping |
| `tests/integration/test_thinking_strip_mock.py` | New: Mock integration test |
| `tests/integration/test_thinking_strip_deepseek.py` | New: DeepSeek-R1 integration test |
| `tests/integration/test_thinking_strip_lms.py` | New: LM Studio integration test |

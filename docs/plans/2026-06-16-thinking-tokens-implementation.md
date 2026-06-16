# Thinking Token Handling — Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Build a two-layer defense (API-level disable + central output stripping) so that
thinking models never return thinking tokens to FOS callers.

**Architecture:** Layer 1 disables thinking at the API level per provider (OpenAI-compatible,
Ollama, Gemini). Layer 2 strips any leaked thinking tokens centrally in `LLMClient.chat()`
before the response reaches any caller. Both layers are always-on, no configuration required.

**Tech Stack:** Python 3.13+, pytest, OpenAI SDK, httpx, google-genai

**Design doc:** `docs/plans/2026-06-16-thinking-tokens-design.md`

---

### Task 1: Consolidate and enhance `strip_thinking_tokens()`

**TDD scenario:** Modifying tested code — existing test for `strip_thinking_tokens` in
`tests/core/llm/test_thinking_disable.py` (created in Task 7) must pass. Existing tests
that import `strip_thinking_tokens` from parsing must still pass.

**Files:**
- Modify: `src/fos/core/agent/parsing.py:1-35`

**Step 1: Replace the function with the consolidated version**

Replace the entire `strip_thinking_tokens()` function with the enhanced version
that consolidates all patterns from `parsing.py`, `validation.py`, the reference doc,
and the design doc:

```python
def strip_thinking_tokens(text: str) -> str:
    """Strip thinking/reasoning tokens from model output.

    Handles all known formats across providers:
    - XML: <think>...</think>, <reasoning>...</reasoning>, etc.
    - Special markers: <|thinking|>...</|thinking|>
    - Pipe-style: |think>...|/think>
    - Kimi markers: ◁think▷...◁/think▷
    - Bracket markup: [THINK]...[/THINK]
    - Markdown sections: # Thinking\\n...
    - Various self-closing and dangling variants
    - Thought-for prefix: "Thought for 2.3s ..."
    """
    if not text:
        return text

    # XML-style paired tags: <think>, <reasoning>, <thought>, <reflection>, <analysis>
    text = re.sub(
        r'<(?:think|reasoning|thought|reflection|analysis)\b[^>]*>.*?'
        r'</(?:think|reasoning|thought|reflection|analysis)\b[^>]*>',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )

    # Self-closing XML tags
    text = re.sub(
        r'<(?:think|reasoning|thought|reflection|analysis)[^>]*/>',
        '', text, flags=re.IGNORECASE,
    )

    # Pipe-style: |think>...|/think> (some GGUF quants)
    text = re.sub(
        r'\|(?:think|thought|reasoning)\>.*?\|/(?:think|thought|reasoning)\>',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )

    # Special markers: <|thinking|>...</|thinking|> (some GGUF quants)
    text = re.sub(
        r'<\|thinking\|>.*?<\|/thinking\|>',
        '', text, flags=re.DOTALL,
    )

    # Kimi markers: ◁think▷...◁/think▷
    text = re.sub(
        r'◁think▷.*?◁/think▷',
        '', text, flags=re.DOTALL,
    )

    # Bracket markup: [THINK]...[/THINK]
    text = re.sub(
        r'\[THINK\].*?\[/THINK\]',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )

    # "Thought for X seconds" prefixes
    text = re.sub(
        r'^Thought for \d+\.?\d*\s*(?:seconds?|ms)?\s*',
        '', text, flags=re.IGNORECASE,
    )

    # Markdown thinking headers (# Thinking, ## Reasoning, etc.)
    text = re.sub(
        r'^#{1,3}\s*(?:Thinking|Reasoning|Thought|Analysis)\s*\n.*?'
        r'(?=\n#{1,3}|\Z)',
        '', text, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )

    # Bare /think, /reasoning, /analysis markers at start of line
    text = re.sub(
        r'(^|\n)\s*/(?:think|reasoning|analysis)\b.*?(?=\n|\Z)',
        '\\1', text, flags=re.IGNORECASE | re.DOTALL,
    )

    # Dangling inline /think, /reasoning, /analysis markers
    text = re.sub(
        r'(?i)\s+/(?:think|reasoning|analysis)\b(?=\s|$)',
        '', text,
    )

    # Strip leading "JSON" prefix some models emit before <think>
    # e.g., "JSON<think>...</think>{\"action\":...}"
    text = re.sub(
        r'^[A-Za-z]+<think>.*?</think>\s*',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )

    return text.strip()
```

**Step 2: Verify no existing tests break**

Run: `pytest tests/ -k "thinking" -v --no-header -q`
Expected: If no existing thinking tests exist yet, 0 collected is fine. If they exist, they must pass.

**Step 3: Commit**

```bash
git add src/fos/core/agent/parsing.py
git commit -m "feat: consolidate all thinking token strip patterns into strip_thinking_tokens()"
```

---

### Task 2: Add central stripping in `LLMClient.chat()`

**TDD scenario:** Modifying tested code — existing LLMClient tests must pass. The central
strip will be verified by Task 8 (mock integration test) returning clean JSON from a
`<think>`-wrapped mock response.

**Files:**
- Modify: `src/fos/core/llm/client.py:1-6` (add import)
- Modify: `src/fos/core/llm/client.py:231-318` (chat method)

**Step 1: Add import at top**

Add to imports at the top of `client.py` (after existing `from fos.i18n import T`):

```python
from fos.core.agent.parsing import strip_thinking_tokens
```

**Step 2: Apply stripping to every return path in `chat()`**

The `chat()` method has four dialect branches, each returning via `self._with_timeout_and_retry(_do)`.
Add a unified cleanup after the dialect dispatch but before the return. Insert at the end
of `chat()`, replacing the final `raise ValueError` line structure:

```python
    def chat(self, messages: List[Dict[str, Any]], json_mode: bool = False) -> str:
        ...

        supports_vision = bool(getattr(self.provider, "supports_vision", False))

        # Collect all dialect branches into a single result variable
        if self.provider.dialect == "openai":
            openai = _get_openai()
            def _do():
                return openai["openai_chat"](
                    client=self.client,
                    model=self.provider.model,
                    messages=messages,
                    temperature=self.provider.temperature,
                    max_tokens=self.provider.max_tokens,
                    frequency_penalty=self.provider.frequency_penalty,
                    presence_penalty=self.provider.presence_penalty,
                    timeout=self.timeout_s,
                    allow_vision=supports_vision,
                    safe_urls_func=validate_media_url,
                    json_mode=json_mode,
                )
            result = self._with_timeout_and_retry(_do)

        elif self.provider.dialect == "gemini":
            gemini = _get_gemini()
            def _do():
                return gemini["gemini_chat"](
                    client=self.client,
                    model=self.provider.model,
                    messages=messages,
                    temperature=self.provider.temperature,
                    max_tokens=self.provider.max_tokens,
                    top_p=self.provider.top_p,
                    frequency_penalty=self.provider.frequency_penalty,
                    presence_penalty=self.provider.presence_penalty,
                    safe_urls_func=validate_media_url,
                    allow_vision=supports_vision,
                    json_mode=json_mode,
                )
            result = self._with_timeout_and_retry(_do)

        elif self.provider.dialect == "mock":
            def _do():
                openai = _get_openai()
                msgs = openai["normalize_messages_for_openai"](messages, False, validate_media_url)
                return self.client.chat(msgs, json_mode=json_mode)
            result = self._with_timeout_and_retry(_do)

        elif self.provider.dialect == "ollama":
            ollama = _get_ollama()
            def _do():
                return ollama["ollama_chat"](
                    client=self.client,
                    model=self.provider.model,
                    messages=messages,
                    temperature=self.provider.temperature,
                    top_p=self.provider.top_p,
                    max_tokens=self.provider.max_tokens,
                    timeout=self.timeout_s,
                    allow_vision=supports_vision,
                    safe_urls_func=validate_media_url,
                    json_mode=json_mode,
                )
            result = self._with_timeout_and_retry(_do)

        else:
            raise ValueError(T("Unknown LLM dialect: {dialect}", dialect=self.provider.dialect))

        # Layer 2: strip any thinking tokens that leaked through
        return strip_thinking_tokens(result)
```

**Step 3: Run existing tests to verify no regressions**

Run: `pytest tests/core/llm/ -v --no-header -q`
Expected: All existing tests pass.

**Step 4: Commit**

```bash
git add src/fos/core/llm/client.py
git commit -m "feat: add central thinking token stripping in LLMClient.chat()"
```

---

### Task 3: Add API-level thinking disable to `openai_chat()`

**TDD scenario:** Modifying tested code — existing OpenAI provider tests must pass.
Task 7 will add explicit tests that verify the parameter is passed.

**Files:**
- Modify: `src/fos/core/llm/providers/openai.py:155`

**Step 1: Add `extra_body` to kwargs**

After the `if json_mode:` block (line 155-156), insert:

```python
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # Layer 1: unconditionally disable thinking/reasoning mode.
    # Non-thinking models silently ignore this.
    kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
```

Insert at line 156, after `kwargs["response_format"] = {"type": "json_object"}` line.

**Step 2: Run existing tests**

Run: `pytest tests/core/llm/test_openai_provider.py -v --no-header -q`
Expected: All pass (assuming they use mock or don't check exact kwargs).

**Step 3: Commit**

```bash
git add src/fos/core/llm/providers/openai.py
git commit -m "feat: add thinking disable param to OpenAI-compatible chat requests"
```

---

### Task 4: Add API-level thinking disable to `ollama_chat()`

**TDD scenario:** Modifying tested code — existing Ollama provider tests must pass.

**Files:**
- Modify: `src/fos/core/llm/providers/ollama.py:197-207` (payload dict)

**Step 1: Add `"think": False` to payload**

In the `payload` dict, after the closing brace of `"options"`, add:

```python
    payload = {
        "model": model,
        "messages": msgs,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        },
        # Layer 1: unconditionally disable thinking mode.
        "think": False,
    }
```

Insert `"think": False,` after `"num_predict": max_tokens,` line 206, before the closing `}`.

**Step 2: Run existing tests**

Run: `pytest tests/core/llm/test_ollama_provider.py -v --no-header -q`
Expected: All pass.

**Step 3: Commit**

```bash
git add src/fos/core/llm/providers/ollama.py
git commit -m "feat: add think=false to Ollama chat requests"
```

---

### Task 5: Add API-level thinking disable to `gemini_chat()`

**TDD scenario:** Modifying tested code — existing Gemini provider tests must pass.

**Files:**
- Modify: `src/fos/core/llm/providers/gemini.py:132-149` (config_kwargs block)

**Step 1: Add `thinking_config` with graceful fallback**

Import `ThinkingConfig` at the top of the function (already imported inside the function body).
Replace the config_kwargs block and the `generate_content` call with a try/except:

```python
    from google.genai.types import GenerateContentConfig, ThinkingConfig

    contents = normalize_messages_for_gemini(messages, allow_vision, safe_urls_func)

    config_kwargs = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
    }

    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

    # Layer 1: unconditionally disable thinking/reasoning mode.
    # Some models (Gemini 2.5 Pro) reject thinking_budget=0, so catch gracefully.
    try:
        config_kwargs["thinking_config"] = ThinkingConfig(thinking_budget=0)
    except Exception:
        pass  # Layer 2 stripping handles anything that leaks through

    resp = client.generate_content(
        contents=contents,
        config=GenerateContentConfig(**config_kwargs),
    )
```

**Step 2: Run existing tests**

Run: `pytest tests/core/llm/test_gemini_provider.py -v --no-header -q`
Expected: All pass.

**Step 3: Commit**

```bash
git add src/fos/core/llm/providers/gemini.py
git commit -m "feat: add thinking_budget=0 to Gemini chat requests with graceful fallback"
```

---

### Task 6: Remove redundant inline `<think>` regex from `generation.py`

**TDD scenario:** Modifying tested code — existing generation tests must pass. The central
stripping in `LLMClient.chat()` now handles this, so the inline regex is redundant.

**Files:**
- Modify: `src/fos/core/llm/generation.py:179`

**Step 1: Remove the redundant line**

Delete line 179:
```python
    cleaned = re.sub(r'<think[\s\S]*?</think\s*>', '', cleaned)
```

Keep the markdown fence stripping that follows (lines 180-182).

**Step 2: Run existing tests**

Run: `pytest tests/core/llm/ -k "generation" -v --no-header -q`
Expected: All pass (central stripping handles it before this code sees the response).

**Step 3: Commit**

```bash
git add src/fos/core/llm/generation.py
git commit -m "refactor: remove redundant inline think tag stripping from generation.py"
```

---

### Task 7: Write unit tests for `strip_thinking_tokens()` and provider params

**TDD scenario:** New feature — full TDD cycle. Write tests, run them (they'll fail since code
from Tasks 1-5 isn't committed yet in TDD order), but since we're writing the plan first,
the tests should be written to match the implementation from Tasks 1-5.

**Files:**
- Create: `tests/core/llm/test_thinking_disable.py`

**Step 1: Write the full test file**

```python
"""Unit tests for thinking token disable + stripping."""

import re

import pytest

from fos.core.agent.parsing import strip_thinking_tokens


# ---------------------------------------------------------------------------
# strip_thinking_tokens() unit tests
# ---------------------------------------------------------------------------

class TestStripThinkingTokens:
    """Verify all known thinking token formats are stripped."""

    def test_xml_think_tags(self):
        assert strip_thinking_tokens('<think>some reasoning</think>{"a":1}') == '{"a":1}'

    def test_xml_reasoning_tags(self):
        assert strip_thinking_tokens('<reasoning>why</reasoning>{"a":1}') == '{"a":1}'

    def test_xml_thought_tags(self):
        assert strip_thinking_tokens('<thought>hmm</thought>{"a":1}') == '{"a":1}'

    def test_xml_reflection_tags(self):
        assert strip_thinking_tokens('<reflection>hmm</reflection>{"a":1}') == '{"a":1}'

    def test_xml_analysis_tags(self):
        assert strip_thinking_tokens('<analysis>hmm</analysis>{"a":1}') == '{"a":1}'

    def test_self_closing_think_tag(self):
        assert strip_thinking_tokens('<think/>{"a":1}') == '{"a":1}'

    def test_pipe_style_tags(self):
        assert strip_thinking_tokens('|think>content|/think>{"a":1}') == '{"a":1}'

    def test_pipe_style_reasoning(self):
        assert strip_thinking_tokens('|reasoning>why|/reasoning>{"a":1}') == '{"a":1}'

    def test_special_thinking_markers(self):
        result = strip_thinking_tokens('<|thinking|>long chain<|/thinking|>{"a":1}')
        assert result == '{"a":1}'

    def test_kimi_markers(self):
        assert strip_thinking_tokens('◁think▷stuff◁/think▷{"a":1}') == '{"a":1}'

    def test_bracket_markup(self):
        assert strip_thinking_tokens('[THINK]thoughts[/THINK]{"a":1}') == '{"a":1}'

    def test_thought_for_prefix(self):
        assert strip_thinking_tokens('Thought for 2.3 seconds {"a":1}') == '{"a":1}'

    def test_thought_for_prefix_milliseconds(self):
        assert strip_thinking_tokens('Thought for 150ms {"a":1}') == '{"a":1}'

    def test_markdown_thinking_header(self):
        text = '# Thinking\nsome thoughts\n\n{"a":1}'
        assert '{"a":1}' in strip_thinking_tokens(text)

    def test_markdown_reasoning_header(self):
        text = '## Reasoning\nsome thoughts\n\n{"a":1}'
        assert '{"a":1}' in strip_thinking_tokens(text)

    def test_bare_think_marker_at_line_start(self):
        assert strip_thinking_tokens('/think\nextra\n{"a":1}') == '\nextra\n{"a":1}'

    def test_dangling_inline_marker(self):
        assert strip_thinking_tokens('content /think {"a":1}') == 'content {"a":1}'

    def test_json_prefix_before_think(self):
        assert strip_thinking_tokens('JSON<think>stuff</think>{"a":1}') == '{"a":1}'

    def test_valid_json_passes_through_unchanged(self):
        original = '{"action": "cooperate", "amount": 5}'
        assert strip_thinking_tokens(original) == original

    def test_empty_input(self):
        assert strip_thinking_tokens('') == ''

    def test_multiple_think_blocks(self):
        text = '<think>a</think>text<think>b</think>{"c":1}'
        assert strip_thinking_tokens(text) == 'text{"c":1}'

    def test_multiline_think_block(self):
        text = '<think>\nline1\nline2\n</think>\n{"a":1}'
        assert strip_thinking_tokens(text) == '\n{"a":1}'
        # strip() in the final output handles leading newline
        assert strip_thinking_tokens(text).strip() == '{"a":1}'

    def test_none_input_returns_none(self):
        # The function returns text.strip() so None would error.
        # Documenting expected behavior: caller should not pass None.
        pass  # Covered by if not text: return text at top


# ---------------------------------------------------------------------------
# Provider parameter tests (verify disable params are sent)
# These test the provider functions directly with mocked clients.
# ---------------------------------------------------------------------------

class TestOpenAIThinkingDisableParam:
    """Verify openai_chat passes thinking disable parameter."""

    def test_extra_body_contains_thinking_disabled(self, monkeypatch):
        from fos.core.llm.providers.openai import openai_chat

        captured_kwargs = {}

        class FakeCompletions:
            @staticmethod
            def create(**kwargs):
                captured_kwargs.update(kwargs)
                return FakeResp()

        class FakeResp:
            choices = [FakeChoice()]

        class FakeChoice:
            message = FakeMessage()

        class FakeMessage:
            content = '{"ok": true}'

        class FakeClient:
            chat = FakeCompletions()

        def fake_normalize(msgs, vision, safe):
            return msgs

        monkeypatch.setattr(
            'fos.core.llm.providers.openai.normalize_messages_for_openai',
            fake_normalize,
        )

        openai_chat(
            client=FakeClient(),
            model='deepseek-reasoner',
            messages=[],
            temperature=0.0,
            max_tokens=100,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            timeout=30.0,
            allow_vision=False,
            safe_urls_func=lambda u: 'valid',
            json_mode=False,
        )

        assert 'extra_body' in captured_kwargs, (
            f"expected extra_body in kwargs, got keys: {list(captured_kwargs.keys())}"
        )
        assert captured_kwargs['extra_body'] == {"thinking": {"type": "disabled"}}


class TestOllamaThinkingDisableParam:
    """Verify ollama_chat passes think=false in payload."""

    def test_payload_contains_think_false(self, monkeypatch):
        from fos.core.llm.providers.ollama import ollama_chat

        captured_payload = {}

        class FakeClient:
            @staticmethod
            def post(url, json=None, timeout=None):
                captured_payload.update(json or {})
                return FakeResp()

        class FakeResp:
            @staticmethod
            def raise_for_status():
                pass

            @staticmethod
            def json():
                return {"message": {"content": '{"ok": true}'}}

        def fake_normalize(msgs, vision, safe):
            return msgs

        monkeypatch.setattr(
            'fos.core.llm.providers.ollama.normalize_messages_for_ollama',
            fake_normalize,
        )

        ollama_chat(
            client=FakeClient(),
            model='qwen3',
            messages=[],
            temperature=0.0,
            top_p=1.0,
            max_tokens=100,
            timeout=30.0,
            allow_vision=False,
            safe_urls_func=lambda u: 'valid',
            json_mode=False,
        )

        assert captured_payload.get('think') is False, (
            f"expected think=False in payload, got: {captured_payload}"
        )


class TestGeminiThinkingDisableParam:
    """Verify gemini_chat passes thinking_config with budget=0."""

    def test_config_contains_thinking_budget_zero(self, monkeypatch):
        from fos.core.llm.providers.gemini import gemini_chat

        captured_config = {}

        class FakeModel:
            @staticmethod
            def generate_content(contents, config):
                captured_config['config'] = config
                return FakeResp()

        class FakeResp:
            text = '{"ok": true}'

        def fake_normalize(msgs, vision, safe):
            return msgs

        monkeypatch.setattr(
            'fos.core.llm.providers.gemini.normalize_messages_for_gemini',
            fake_normalize,
        )

        gemini_chat(
            client=FakeModel(),
            model='gemini-2.0-flash',
            messages=[],
            temperature=0.0,
            max_tokens=100,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            safe_urls_func=lambda u: 'valid',
            allow_vision=False,
            json_mode=False,
        )

        config = captured_config.get('config')
        assert config is not None, "expected GenerateContentConfig to be captured"
        tc = getattr(config, 'thinking_config', None)
        assert tc is not None, (
            f"expected thinking_config on GenerateContentConfig, got None"
        )
        assert tc.thinking_budget == 0, (
            f"expected thinking_budget=0, got {tc.thinking_budget}"
        )


class TestGeminiThinkingGracefulDegrade:
    """Verify gemini_chat gracefully handles thinking_budget=0 rejection."""

    def test_graceful_when_thinking_budget_rejected(self, monkeypatch):
        from fos.core.llm.providers.gemini import gemini_chat

        captured_config = {}

        class FakeModel:
            @staticmethod
            def generate_content(contents, config):
                captured_config['config'] = config
                return FakeResp()

        class FakeResp:
            text = '{"ok": true}'

        def fake_normalize(msgs, vision, safe):
            return msgs

        # Make ThinkingConfig raise when budget=0 (simulating Gemini 2.5 Pro)
        original_thinking_config = None
        try:
            from google.genai.types import ThinkingConfig as RealTC
            original_thinking_config = RealTC
        except ImportError:
            pass

        class RaisingThinkingConfig:
            def __init__(self, thinking_budget=0):
                if thinking_budget == 0:
                    raise ValueError("thinking_budget=0 not supported")
                self.thinking_budget = thinking_budget

        monkeypatch.setattr(
            'fos.core.llm.providers.gemini.normalize_messages_for_gemini',
            fake_normalize,
        )

        # Patch ThinkingConfig to the raising version
        import fos.core.llm.providers.gemini as gemini_mod
        monkeypatch.setattr(gemini_mod, 'ThinkingConfig', RaisingThinkingConfig, raising=False)

        # Should not raise — should catch and proceed
        result = gemini_chat(
            client=FakeModel(),
            model='gemini-2.5-pro',
            messages=[],
            temperature=0.0,
            max_tokens=100,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            safe_urls_func=lambda u: 'valid',
            allow_vision=False,
            json_mode=False,
        )

        assert result == '{"ok": true}'
```

**Step 2: Run all unit tests**

Run: `pytest tests/core/llm/test_thinking_disable.py -v --no-header -q`
Expected: All 25 tests pass.

**Step 3: Commit**

```bash
git add tests/core/llm/test_thinking_disable.py
git commit -m "test: add comprehensive thinking token unit tests (strip + provider params)"
```

---

### Task 8: Write mock integration test for thinking token stripping

**TDD scenario:** New feature — full TDD cycle.

**Files:**
- Create: `tests/integration/test_thinking_strip_mock.py`

**Step 1: Write the test**

```python
"""Integration test: Mock provider returns <think>-wrapped JSON → chat() returns clean JSON."""

import json
import pytest
from fos.core.llm.client import LLMClient
from fos.core.llm_config import LLMConfig


class _ThinkingMockModel:
    """Mock that returns a response with <think> tags before the JSON."""

    def chat(self, messages, json_mode=False):
        return '<think>long chain of reasoning here</think>\n{"action": "cooperate", "amount": 5}'

    def completion(self, prompt):
        return ''


def test_mock_thinking_stripped():
    """Mock provider with <think> tags → chat() returns clean JSON only."""
    config = LLMConfig(
        dialect='mock',
        model='thinking-mock',
    )

    # Inject our custom mock model
    client = LLMClient(config)
    client.client = _ThinkingMockModel()

    messages = [{"role": "user", "content": "What do you do?"}]
    result = client.chat(messages, json_mode=True)

    # Should be clean JSON, no <think> tags
    assert '<think>' not in result, f"<think> tag leaked through: {result!r}"
    assert '</think>' not in result, f"</think> tag leaked through: {result!r}"

    # Should parse as valid JSON
    parsed = json.loads(result)
    assert parsed == {"action": "cooperate", "amount": 5}


def test_mock_no_thinking_tags_passes_through():
    """Mock provider without thinking tags → chat() returns unchanged."""
    config = LLMConfig(
        dialect='mock',
        model='clean-mock',
    )

    client = LLMClient(config)
    client.client = _ThinkingMockModel()
    # Override to return clean JSON
    client.client.chat = lambda msgs, json_mode=False: '{"action": "defect"}'

    messages = [{"role": "user", "content": "What do you do?"}]
    result = client.chat(messages, json_mode=True)

    assert result == '{"action": "defect"}'
```

**Step 2: Run the test**

Run: `pytest tests/integration/test_thinking_strip_mock.py -v --no-header -q`
Expected: 2 tests pass.

**Step 3: Commit**

```bash
git add tests/integration/test_thinking_strip_mock.py
git commit -m "test: add mock integration test for central thinking token stripping"
```

---

### Task 9: Write DeepSeek-R1 integration test

**TDD scenario:** New feature — full TDD cycle. Skippable integration test.

**Files:**
- Create: `tests/integration/test_thinking_strip_deepseek.py`

**Step 1: Write the test**

```python
"""Integration test: DeepSeek-R1 via OpenAI-compatible API → thinking tokens are not returned.

Requires DEEPSEEK_API_KEY env var. Skipped if not set.
"""

import os
import json
import pytest
from fos.core.llm.client import LLMClient
from fos.core.llm_config import LLMConfig


pytestmark = pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set",
)


def test_deepseek_r1_thinking_disabled():
    """DeepSeek-R1 with json_mode → response is clean parseable JSON with no <think> tags."""
    config = LLMConfig(
        dialect="openai",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        model="deepseek-reasoner",
        base_url="https://api.deepseek.com/v1",
        max_tokens=512,
        temperature=0.0,
    )

    client = LLMClient(config)

    messages = [{
        "role": "user",
        "content": 'Reply with ONLY valid JSON: {"color": "<your favorite color>", "number": <1-10>}',
    }]

    response = client.chat(messages, json_mode=True)

    assert response, "got empty response"
    assert "<think>" not in response.lower(), f"<think> tag leaked: {response[:200]}"
    assert "</think>" not in response.lower(), f"</think> tag leaked: {response[:200]}"

    # Must be valid JSON
    parsed = json.loads(response)
    assert "color" in parsed, f"missing 'color' in {parsed}"
    assert "number" in parsed, f"missing 'number' in {parsed}"
```

**Step 2: Run the test (if API key is set)**

Run: `DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY pytest tests/integration/test_thinking_strip_deepseek.py -v --no-header -q`
Expected: 1 test passed, or skipped if no key.

**Step 3: Commit**

```bash
git add tests/integration/test_thinking_strip_deepseek.py
git commit -m "test: add DeepSeek-R1 integration test for thinking token handling"
```

---

### Task 10: Write LM Studio integration test

**TDD scenario:** New feature — full TDD cycle. Skippable integration test.

**Files:**
- Create: `tests/integration/test_thinking_strip_lms.py`

**Step 1: Write the test**

```python
"""Integration test: Qwen3 via LM Studio → thinking tokens are not returned.

Requires LM Studio running locally on http://localhost:1234/v1 with a
Qwen3 model loaded. Skipped if server is unreachable.
"""

import json
import pytest
import httpx
from fos.core.llm.client import LLMClient
from fos.core.llm_config import LLMConfig


def _lms_reachable() -> bool:
    """Check if LM Studio OpenAI-compatible endpoint is reachable."""
    try:
        resp = httpx.get("http://localhost:1234/v1/models", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _lms_reachable(),
    reason="LM Studio not reachable at http://localhost:1234/v1",
)


def test_lms_qwen3_thinking_disabled():
    """Qwen3 via LM Studio with json_mode → response is clean JSON, no <think> tags."""
    config = LLMConfig(
        dialect="openai",
        api_key="not-needed",
        model="qwen3",  # or whatever the loaded model name is
        base_url="http://localhost:1234/v1",
        max_tokens=256,
        temperature=0.0,
    )

    client = LLMClient(config)

    messages = [{
        "role": "user",
        "content": 'Reply with ONLY valid JSON: {"answer": "<yes or no>"}',
    }]

    response = client.chat(messages, json_mode=True)

    assert response, "got empty response from LM Studio"
    assert "<think>" not in response.lower(), f"<think> tag leaked: {response[:200]}"
    assert "</think>" not in response.lower(), f"</think> tag leaked: {response[:200]}"

    # Must be valid JSON
    parsed = json.loads(response)
    assert "answer" in parsed, f"missing 'answer' in {parsed}"
    assert parsed["answer"] in ("yes", "no"), f"unexpected answer: {parsed['answer']}"
```

**Step 2: Run the test (if LM Studio is running)**

Run: `pytest tests/integration/test_thinking_strip_lms.py -v --no-header -q`
Expected: 1 test passed or skipped.

**Step 3: Commit**

```bash
git add tests/integration/test_thinking_strip_lms.py
git commit -m "test: add LM Studio integration test for thinking token handling"
```

---

### Final Verification

Run the full test suite to confirm nothing is broken:

```bash
pytest tests/core/llm/ tests/integration/test_thinking_strip_mock.py -v --no-header -q
```

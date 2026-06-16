"""Integration test: Qwen3 via LM Studio (lms) local server.

Verifies thinking tokens are stripped from a real thinking-capable model
running on LM Studio's OpenAI-compatible endpoint.

Requires LM Studio running on http://127.0.0.1:1234/v1 with a thinking-capable
model (e.g., qwen/qwen3.6-35b-a3b) loaded. Skipped if server is unreachable.
"""

import json

import pytest


def _lms_reachable() -> bool:
    """Check if LM Studio OpenAI-compatible endpoint is reachable."""
    try:
        import httpx

        resp = httpx.get("http://127.0.0.1:1234/v1/models", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _lms_reachable(),
    reason="LM Studio not reachable at http://127.0.0.1:1234/v1",
)


def test_lms_thinking_disabled():
    """Model via LM Studio with json_mode -> response is clean JSON, no <think> tags."""
    pytest.importorskip("openai")
    from fos.core.llm.client import LLMClient
    from fos.core.llm_config import LLMConfig

    config = LLMConfig(
        dialect="openai",
        api_key="not-needed",
        model="qwen/qwen3.6-35b-a3b",
        base_url="http://127.0.0.1:1234/v1",
        max_tokens=512,
        temperature=0.1,
    )

    client = LLMClient(config)

    messages = [
        {
            "role": "user",
            "content": 'Reply with ONLY valid JSON: {"answer": "<yes or no>"}',
        }
    ]

    response = client.chat(messages, json_mode=True)

    assert response, "got empty response from LM Studio"
    assert "<think>" not in response.lower(), f"<think> tag leaked: {response[:200]}"
    assert "</think>" not in response.lower(), f"</think> tag leaked: {response[:200]}"

    parsed = json.loads(response)
    assert "answer" in parsed, f"missing 'answer' in {parsed}"
    assert parsed["answer"] in ("yes", "no"), f"unexpected answer: {parsed['answer']}"

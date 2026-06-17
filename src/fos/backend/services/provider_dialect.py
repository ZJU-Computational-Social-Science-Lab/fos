from __future__ import annotations


# Dialects with OpenAI-compatible APIs — all normalize to "openai" for FOS internals.
_OPENAI_COMPATIBLE_NORMALIZED = {
    "openai-compatible",
    "deepseek",
    "lmstudio",
    "vllm",
    "llamacpp",
    "groq",
    "together",
    "fireworks",
    "openrouter",
}


def normalize_provider_dialect(raw: str | None) -> str:
    value = (raw or "").strip().lower().replace("_", "-")
    if value in _OPENAI_COMPATIBLE_NORMALIZED:
        return "openai"
    return value

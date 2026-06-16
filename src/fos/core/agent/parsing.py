"""Minimal parsing utilities for legacy Agent output.

Provides strip_thinking_tokens for cleaning LLM responses.
See docs/plans/policy-cascade-port-investigation.md

Contains: strip_thinking_tokens
"""

import re


def strip_thinking_tokens(text: str) -> str:
    """Strip thinking/reasoning tokens from model output.

    Handles all known formats across providers:
    - XML: <think>...</think>, <reasoning>...</reasoning>, etc.
    - Special markers: <|thinking|>...</|thinking|>
    - Pipe-style: |think>...|/think>
    - Kimi markers: ◁think▷...◁/think▷
    - Bracket markup: [THINK]...[/THINK]
    - Markdown sections: # Thinking\n...
    - Various self-closing and dangling variants
    - Thought-for prefix: "Thought for 2.3s ..."
    """
    if not text:
        return text

    # Strip leading "JSON" prefix some models emit before <think>
    # Runs BEFORE XML strip so it catches "JSON<think>...</think>{\"action\":...}"
    # as a unit before the XML regex strips the inner <think> block.
    text = re.sub(
        r'^[A-Za-z]+<think>.*?</think>\s*',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )

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
    # Stop at next header (*#) or blank line (\n\s*\n).
    text = re.sub(
        r'^#{1,3}\s*(?:Thinking|Reasoning|Thought|Analysis)\b[^\n]*\n.*?'
        r'(?=\n#{1,3}|\n\s*\n|\Z)',
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

    return text.strip()

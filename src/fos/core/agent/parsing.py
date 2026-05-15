"""Minimal parsing utilities for legacy Agent output.

Provides strip_thinking_tokens for cleaning LLM responses.
See docs/plans/policy-cascade-port-investigation.md

Contains: strip_thinking_tokens
"""

import re


def strip_thinking_tokens(text: str) -> str:
    """Strip thinking/reasoning tokens from model output."""
    if not text:
        return text
    # XML-style thinking tags
    text = re.sub(
        r'<(?:think|reasoning|thought|reflection|analysis)\b[^>]*>.*?</(?:think|reasoning|thought|reflection|analysis)\b[^>]*>',
        '', text, flags=re.DOTALL | re.IGNORECASE,
    )
    # Self-closing tags
    text = re.sub(r'<(?:think|reasoning|thought|reflection|analysis)[^>]*/>', '', text, flags=re.IGNORECASE)
    # Pipe-style tags
    text = re.sub(r'\|(?:think|thought|reasoning)\>.*?\|/(?:think|thought|reasoning)\>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # "Thought for X seconds" prefixes
    text = re.sub(r'^Thought for \d+\.?\d*\s*(?:seconds?|ms)?\s*', '', text, flags=re.IGNORECASE)
    # Markdown thinking headers
    text = re.sub(r'^#{1,3}\s*(?:Thinking|Reasoning|Thought|Analysis)\s*\n.*?(?=\n#{1,3}|\Z)', '', text, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)
    # Bare /think markers
    text = re.sub(r'(^|\n)\s*/(?:think|reasoning|analysis)\b.*?(?=\n|\Z)', '\\1', text, flags=re.IGNORECASE | re.DOTALL)
    # Dangling inline reasoning markers
    text = re.sub(r'(?i)\s+/(?:think|reasoning|analysis)\b(?=\s|$)', '', text)
    return text.strip()

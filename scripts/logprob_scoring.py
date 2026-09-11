#!/usr/bin/env python3
"""Read the model's own purchase probability from llama-server logprobs.

R1LP is the logprob version of the 5-model experiment: instead of sampling
many grammar-constrained draws, it asks the model once per prompt for the
probability it assigns to "purchase" versus "not purchase", with no
grammar. This module owns the two scoring mechanisms and every parsing and
arithmetic step they need. It never starts a run and never loads a model;
the HTTP call is an injectable `post` function so every test can run fully
offline against a fake transport.

The two mechanisms (chosen with --logprob-mode):
    first_token - ONE call per prompt: POST /v1/chat/completions
        with a short max_tokens window (the decision scan),
        temperature=1.0, logprobs=true, top_logprobs=20. The parser walks
        the generated tokens, SKIPS control/channel tokens and reads the
        top-logprobs at the FIRST substantive answer position: p_buy
        (tokens that continue "purchase"), p_nobuy (tokens that start
        "not") and their sum branch_mass; a flag records when neither
        branch is in the top-k.
    candidate_scoring (default) - TWO calls per prompt (one per
        candidate): POST /completions with the chat-templated prompt plus
        the candidate
        appended, n_predict=0, logprobs=true, n_probs=20, temperature=1.0.
        The candidate's own token logprobs are summed (lp_sum), counted and
        length-normalized (lp_mean); a 2-way softmax turns the two
        candidates' scores into p_buy / p_nobuy (plus a length-normalized
        variant).

The exact llama-server response shape of /completions is still an open
item: it must be validated with a 2-4 call probe before the real run (see
LOGPROB-DESIGN.md). The parser below therefore tolerates the known
variants (completion_probabilities, prompt_logprobs, per-token
top_logprobs/probs) and always keeps a truncated raw response for audit.

Plain-language function map:
    purchase_branch_mass(...)     - p_buy / p_nobuy / branch_mass from a
                                    top-logprobs list.
    parse_first_token_response()  - the decision position and top-logprobs
                                    out of one /v1/chat/completions reply
                                    (control/channel chosen tokens are
                                    skipped; the first substantive answer
                                    position is measured).
    parse_candidate_response()    - per-token logprobs out of one
                                    /completions reply (all variants).
    sum_candidate_logprobs(...)   - lp_sum / lp_tokens / lp_mean for the
                                    trailing candidate tokens.
    candidate_softmax(...)        - 2-way softmax of the two candidates.
    count_candidate_tokens(...)   - how many trailing tokens a candidate is.
    render_chat_template(...)     - a ChatML rendering of the chat messages.
    make_first_token_scorer(...)  - the first_token scorer.
    make_candidate_scorer(...)    - the candidate_scoring scorer; stamps
                                    the label_order it scored on every
                                    result.
    average_ab_p_buy(...)         - the A/B aggregate: the mean of the two
                                    label orders' p(buy) values.
    make_ab_scorer(...)           - the A/B executor: scores BOTH label
                                    orders per prompt and merges them into
                                    ONE result (averaged p(buy) plus both
                                    raw per-order results under their
                                    label_order stamps).
    make_scorer(...)              - pick one by mode name (ab_orders=True
                                    wraps candidate_scoring in the A/B
                                    executor).
"""

from __future__ import annotations

import json
import math
import re
import urllib.request
from typing import Any, Callable

FIRST_TOKEN = "first_token"
CANDIDATE_SCORING = "candidate_scoring"
LOGP_MODES = (FIRST_TOKEN, CANDIDATE_SCORING)
# USER DIRECTIVE (binding): the R1LP default scoring mode is the
# full-string candidate comparison; first_token only via an explicit flag.
DEFAULT_LOGP_MODE = CANDIDATE_SCORING
TOP_LOGPROBS = 20
N_PROBS = 20
RAW_RESPONSE_LIMIT = 2048  # characters kept for the audit copy
_PURCHASE_CANDIDATE = "purchase"
_NOBUY_CANDIDATE = "not purchase"
# The two A/B label orders (USER DIRECTIVE, binding): an A/B cell is
# scored once with each order - "purchase" asked first, then the
# reversal - so a label-position bias averages out of p(buy) instead of
# skewing it.
AB_LABEL_ORDERS = (
    (_PURCHASE_CANDIDATE, _NOBUY_CANDIDATE),
    (_NOBUY_CANDIDATE, _PURCHASE_CANDIDATE),
)
# The production decision-scan window: how many tokens one first_token
# call generates so the parser can walk past a control-token prefix
# (e.g. Gemma's "<|channel>") to the first substantive answer token. The
# bare make_first_token_scorer primitive keeps the historical 1-token
# default; the make_scorer dispatcher defaults production runs to this.
SCAN_TOKENS = 8
# The built-in control-token shape: special markup tokens such as
# "<|channel>", "<|message>" or "<|end|>". Note the shape must NOT
# require a "|" before the ">" ("<|channel>" has none); per-model extras
# are plain exact strings via the control_tokens extension list.
_CONTROL_MARKUP_RE = re.compile(r"<\|.*>")

PostFn = Callable[[str, dict[str, Any], float], tuple[int, str]]


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, str]:
    """POST one JSON object and return the (status, body) pair.

    The one place this module can open a socket. Tests inject their own
    `post` so no test ever reaches a real server.
    """
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def _server_root(base_url: str) -> str:
    """Normalize a server address: no trailing slash, no doubled /v1."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return root


def _truncate(body: Any) -> str:
    """The audit copy of one response body, truncated to <= 2 KB."""
    text = body if isinstance(body, str) else json.dumps(body, default=str)
    return text[:RAW_RESPONSE_LIMIT]


def _loads(body: Any) -> dict[str, Any]:
    """Decode a response body to a dict; an unreadable body becomes {}."""
    if isinstance(body, dict):
        return body
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    if not isinstance(body, str):
        return {}
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _token_from_entry(entry: dict[str, Any]) -> str | None:
    """The token text of one logprob entry, across the known key names."""
    for key in ("token", "content", "tok_str", "text"):
        value = entry.get(key)
        if isinstance(value, str):
            return value
    return None


def _prob_to_logprob(value: Any) -> float | None:
    """A probability as a logprob (a non-positive probability is invalid)."""
    if not isinstance(value, (int, float)):
        return None
    probability = float(value)
    if probability <= 0.0:
        return None
    return math.log(probability)


def _logprob_from_entry(entry: dict[str, Any], token: str | None) -> float | None:
    """The chosen token's logprob from one entry, across the known variants.

    Reads a direct logprob/lp field; otherwise looks inside a per-token
    `probs` or `top_logprobs` list, preferring the entry that matches the
    chosen token and falling back to the highest-probability candidate.
    """
    for key in ("logprob", "lp"):
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    direct_prob = _prob_to_logprob(entry.get("prob"))
    if direct_prob is not None:
        return direct_prob
    for key in ("probs", "top_logprobs"):
        candidates = entry.get(key)
        if not isinstance(candidates, list) or not candidates:
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if token is not None and candidate.get("tok_str") == token:
                return _prob_to_logprob(candidate.get("prob")) or _candidate_logprob(
                    candidate
                )
        for candidate in candidates:
            if isinstance(candidate, dict):
                value = _candidate_logprob(candidate)
                if value is not None:
                    return value
    return None


def _candidate_logprob(candidate: dict[str, Any]) -> float | None:
    """One candidate's logprob (direct logprob, else log of its prob)."""
    for key in ("logprob", "lp"):
        value = candidate.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return _prob_to_logprob(candidate.get("prob"))


DEFAULT_LABELS = ("purchase", "not purchase")


def _label_heads(labels: tuple[str, str]) -> tuple[str, str]:
    """The exact first word of each label, lower-cased and junk-free.

    A token matches a branch only when its cleaned text equals this head
    word (or continues it at a word boundary for multi-word labels like
    "not purchase", whose head word is "not"). Prefix look-alikes
    ("none" vs "no", "yesterday" vs "yes") are different words and
    never match. A label with no readable word at all matches nothing.
    """
    positive, negative = labels
    clean = lambda text: re.sub(r"^[^0-9a-z]+", "", text.strip().lower())  # noqa: E731

    def head(label: str) -> str:
        words = clean(label).split()
        return words[0] if words else ""

    return head(positive), head(negative)


def _branch_of(
    token: str | None, labels: tuple[str, str] = DEFAULT_LABELS
) -> str | None:
    """Which decision branch a token text belongs to: 'buy', 'nobuy' or None.

    Leading punctuation/whitespace is stripped and the text is lower-cased
    first, so " Purchase", "'purchase" and "purchase" all read as the buy
    branch and " not" as the nobuy branch. The match against the label's
    head word is EXACT (or continues it at a word boundary, so "not
    purchase" still reads as nobuy): a prefix look-alike such as "none",
    "nobody" or "yesterday" is a different word and returns None.
    """
    if not isinstance(token, str):
        return None
    positive_head, negative_head = _label_heads(labels)
    cleaned = re.sub(r"^[^0-9a-z]+", "", token.strip().lower())
    if positive_head and (
        cleaned == positive_head or cleaned.startswith(positive_head + " ")
    ):
        return "buy"
    if negative_head and (
        cleaned == negative_head or cleaned.startswith(negative_head + " ")
    ):
        return "nobuy"
    return None


def purchase_branch_mass(
    top_logprobs: list[dict[str, Any]], labels: tuple[str, str] = DEFAULT_LABELS
) -> dict[str, Any]:
    """Branch probabilities from one decision-position top-k list.

    The tokens whose exact form matches the positive label ("purchase" by
    default, "yes" for the R1-YESNO profile) sum into p_buy/p_yes, and the
    negative label's tokens into p_nobuy/p_no; neither_branch is True when
    neither branch appears at all (so the caller can flag the cell instead
    of guessing a probability). The matched raw token forms are recorded so
    per-model tokenisation quirks (leading space, capitalisation) stay
    visible. Schema continuity: the legacy p_buy/p_nobuy keys keep the
    historical 0.0-when-absent semantics, while the newer p_yes/p_no keys
    are None when a branch is absent - a silent 0.0 would fake a measured
    answer.
    """
    p_buy = 0.0
    p_nobuy = 0.0
    matched_yes: list[str] = []
    matched_no: list[str] = []
    for entry in top_logprobs or []:
        if not isinstance(entry, dict):
            continue
        token = _token_from_entry(entry)
        logprob = _logprob_from_entry(entry, token)
        if logprob is None:
            continue
        probability = math.exp(logprob)
        branch = _branch_of(token, labels)
        if branch == "buy":
            p_buy += probability
            matched_yes.append(token or "")
        elif branch == "nobuy":
            p_nobuy += probability
            matched_no.append(token or "")
    return {
        "p_buy": p_buy,
        "p_nobuy": p_nobuy,
        "p_yes": p_buy if matched_yes else None,
        "p_no": p_nobuy if matched_no else None,
        "branch_mass": p_buy + p_nobuy,
        "neither_branch": p_buy == 0.0 and p_nobuy == 0.0,
        "matched_yes_tokens": matched_yes,
        "matched_no_tokens": matched_no,
    }


def _reply_choice(data: dict[str, Any]) -> dict[str, Any]:
    """The first choice of a chat reply ({} when unreadable)."""
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return {}


def _reply_content(data: dict[str, Any]) -> str:
    """The generated message text of a chat reply ("" when unreadable)."""
    message = _reply_choice(data).get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else ""


def _position_top_k(block: dict[str, Any]) -> list[Any]:
    """One generated position's raw top-k candidate list.

    A position without its own candidate list IS its own single
    candidate: that is the flat shape the single-token parser read.
    """
    candidates = block.get("top_logprobs")
    if isinstance(candidates, list) and candidates:
        return candidates
    return [block]


def _token_positions(data: dict[str, Any]) -> list[tuple]:
    """Every generated token position of a chat reply, in order.

    Each position is (chosen token text or None, chosen logprob or None,
    its raw top-k candidate list). The OpenAI shape walks
    logprobs.content[*] (one block per generated token); the positional
    logprobs.top_logprobs shape (no chosen token per position) becomes
    ONE position, measured the way the single-token parser always read
    it.
    """
    logprobs = _reply_choice(data).get("logprobs")
    if not isinstance(logprobs, dict):
        return []
    content = logprobs.get("content")
    if isinstance(content, list):
        positions: list[tuple] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            token = _token_from_entry(block)
            positions.append(
                (token, _logprob_from_entry(block, token), _position_top_k(block))
            )
        if positions:
            return positions
    positional = logprobs.get("top_logprobs")
    if isinstance(positional, list) and positional:
        first = positional[0]
        if isinstance(first, list):
            return [(None, None, first)]
        if isinstance(first, dict):
            return [(None, None, positional)]
    return []


def _normalize_top_k(candidates: list[Any]) -> list[dict[str, Any]]:
    """The readable {"token", "logprob"} entries of one raw top-k list."""
    top: list[dict[str, Any]] = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        token = _token_from_entry(entry)
        logprob = _logprob_from_entry(entry, token)
        if logprob is None:
            continue
        top.append({"token": token or "", "logprob": float(logprob)})
    return top


def _is_control_token(token: Any, control_tokens: tuple[str, ...]) -> bool:
    """Whether one CHOSEN token is a control/channel token.

    Control by default: the special markup shape ("<|channel>",
    "<|message>", "<|end|>" - the observed Gemma-style openers).
    Per-model extras are exact token strings in `control_tokens`,
    extendable without code changes; ordinary answer words never match.
    """
    if not isinstance(token, str):
        return False
    if _CONTROL_MARKUP_RE.fullmatch(token):
        return True
    return token in control_tokens


def _find_decision_position(
    positions: list[tuple], control_tokens: tuple[str, ...]
) -> tuple[int | None, list[str]]:
    """Walk the CHOSEN tokens; skip control tokens until the answer.

    Returns (0-based index of the first substantive position or None,
    the skipped control tokens in generation order). Only the CHOSEN
    token decides: yes/no candidates hiding in a skipped position's
    top-k are never measured.
    """
    skipped: list[str] = []
    for index, (token, _logprob, _top_k) in enumerate(positions):
        if _is_control_token(token, control_tokens):
            skipped.append(token or "")
            continue
        return index, skipped
    return None, skipped


def parse_first_token_response(
    body: Any,
    labels: tuple[str, str] = DEFAULT_LABELS,
    control_tokens: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Read one /v1/chat/completions reply into the p(buy) fields.

    The reply may carry SEVERAL generated token positions (the decision
    scan asks for a short window). The parser walks the CHOSEN token of
    every position, skips control/channel tokens (the built-in "<|...>"
    markup shape plus the exact `control_tokens` extension list) and
    measures the yes/no mass at the FIRST substantive position's top-k.
    The audit trail names the decision position (`decision_position`,
    1-based; `top_logprobs` stays that position's raw top-k), the
    skipped control tokens in generation order
    (`skipped_prefix`/`skipped_len`), every position's raw top-k
    (`per_position_top_k`) and the extension list in force
    (`control_tokens`). A reply of ONLY control tokens has no decision
    position: `decision_position` is None with
    `no_substantive_position` True and None probabilities - the call
    itself still succeeded (it produced readable logprobs); the
    measurement is honestly None. p_yes_binary is the positive share of
    the two-branch mass, p_yes/(p_yes+p_no); None when neither branch
    appears, never a silent 0.
    """
    data = _loads(body)
    positions = _token_positions(data)
    per_position = [_normalize_top_k(position[2]) for position in positions]
    extension = tuple(control_tokens or ())
    index, skipped = _find_decision_position(positions, extension)
    top = per_position[index] if index is not None else []
    mass = purchase_branch_mass(top, labels)
    total = mass["p_buy"] + mass["p_nobuy"]
    runaway = index is None and bool(positions)
    return {
        "top_logprobs": top,
        "raw_content": _reply_content(data),
        "raw_logprob_response": _truncate(body),
        "p_yes_binary": mass["p_buy"] / total if total > 0.0 else None,
        "neither_branch_in_top_k": bool(mass["neither_branch"]),
        "decision_position": None if index is None else index + 1,
        "skipped_prefix": skipped,
        "skipped_len": len(skipped),
        "per_position_top_k": per_position,
        "control_tokens": list(extension),
        "no_substantive_position": runaway,
        "succeeded": bool(top) or runaway,
        **mass,
    }


def _candidate_entries(data: dict[str, Any]) -> list[dict]:
    """The per-token entries of one /completions reply (all known shapes)."""
    for key in ("completion_probabilities", "prompt_logprobs"):
        value = data.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        logprobs = choices[0].get("logprobs")
        if isinstance(logprobs, dict):
            content = logprobs.get("content")
            if isinstance(content, list):
                return [entry for entry in content if isinstance(entry, dict)]
    return []


def parse_candidate_response(body: Any) -> dict[str, Any]:
    """Read one /completions reply into its per-token logprobs.

    Tolerates `completion_probabilities`, `prompt_logprobs` and per-token
    `top_logprobs`/`probs`; each returned entry carries its token text and
    the chosen-token logprob. Also keeps a truncated raw copy for audit.
    succeeded is True when at least one token logprob was readable.
    """
    data = _loads(body)
    tokens: list[dict[str, Any]] = []
    for entry in _candidate_entries(data):
        token = _token_from_entry(entry)
        logprob = _logprob_from_entry(entry, token)
        if logprob is None and token is None:
            continue
        tokens.append(
            {
                "token": token or "",
                "logprob": float(logprob) if logprob is not None else None,
            }
        )
    return {
        "token_logprobs": tokens,
        "raw_logprob_response": _truncate(body),
        "succeeded": any(entry["logprob"] is not None for entry in tokens),
    }


def sum_candidate_logprobs(
    token_logprobs: list[dict[str, Any]], candidate_token_count: int
) -> dict[str, Any]:
    """Sum exactly the trailing candidate tokens' logprobs.

    The candidate text is appended at the very end of the prompt, so its
    tokens are the last candidate_token_count entries; prompt tokens are
    never included. Returns lp_sum, lp_tokens (how many were summed) and
    the length-normalized lp_mean (None when no token had a logprob).
    """
    entries = list(token_logprobs or [])
    if candidate_token_count and candidate_token_count > 0:
        entries = entries[-candidate_token_count:]
    values = [
        float(entry["logprob"])
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("logprob"), (int, float))
    ]
    if not values:
        return {"lp_sum": None, "lp_tokens": 0, "lp_mean": None}
    total = sum(values)
    return {"lp_sum": total, "lp_tokens": len(values), "lp_mean": total / len(values)}


def candidate_softmax(lp_buy: float | None, lp_nobuy: float | None) -> dict[str, Any]:
    """A 2-way softmax over the two candidate log-scores.

    Returns p_buy and p_nobuy (each None when either score is missing), so
    a cell that failed one candidate is visible instead of silently equal
    to 0.5.
    """
    if lp_buy is None or lp_nobuy is None:
        return {"p_buy": None, "p_nobuy": None}
    largest = max(lp_buy, lp_nobuy)
    exp_buy = math.exp(lp_buy - largest)
    exp_nobuy = math.exp(lp_nobuy - largest)
    total = exp_buy + exp_nobuy
    return {"p_buy": exp_buy / total, "p_nobuy": exp_nobuy / total}


def average_ab_p_buy(forward_p_buy: float, reversed_p_buy: float) -> float:
    """The A/B aggregate of the two label orders' p(buy): their plain mean.

    Both orders ask the very same question, so neither answer is trusted
    more than the other: they are averaged (mean(0.8, 0.2) == 0.5).
    """
    return (forward_p_buy + reversed_p_buy) / 2.0


def count_candidate_tokens(candidate: str) -> int:
    """How many trailing tokens one candidate text is.

    A probe-pending heuristic: "purchase" counts as one token and
    "not purchase" as two, which matches the common tokenizers; the real
    count must be confirmed by the 2-4 call probe described in
    LOGPROB-DESIGN.md.
    """
    return max(1, len(candidate.split()))


def render_chat_template(messages: list[dict[str, Any]]) -> str:
    """Render chat messages as a ChatML prompt ending in the assistant cue.

    llama-server's /completions endpoint takes a raw prompt, so the chat
    messages must be templated locally. This ChatML rendering is the
    documented fallback; the exact template of each model must be confirmed
    by the pre-run probe (LOGPROB-DESIGN.md).
    """
    parts = []
    for message in messages or []:
        role = message.get("role", "user")
        content = message.get("content", "")
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n")
    return "".join(parts)


def _first_token_payload(
    model: str, messages: list[dict[str, Any]], scan_tokens: int = 1
) -> dict[str, Any]:
    """The one-call first_token request: no grammar, logprobs requested.

    max_tokens is the decision-scan window: 1 keeps the historical
    single-token call; a larger window lets the parser walk past
    control/channel tokens to the first substantive answer.
    """
    return {
        "model": model,
        "messages": messages,
        "temperature": 1.0,
        "max_tokens": scan_tokens,
        "logprobs": True,
        "top_logprobs": TOP_LOGPROBS,
    }


def _candidate_payload(model: str, prompt: str) -> dict[str, Any]:
    """The teacher-forced candidate request: n_predict=0, logprobs on."""
    return {
        "model": model,
        "prompt": prompt,
        "temperature": 1.0,
        "n_predict": 0,
        "logprobs": True,
        "n_probs": N_PROBS,
    }


def _unified(first: dict[str, Any]) -> dict[str, Any]:
    """Normalize a first_token parse into the shared scorer schema."""
    return {
        "logprob_mode": FIRST_TOKEN,
        "p_buy_logprob": first.get("p_buy"),
        "p_nobuy_logprob": first.get("p_nobuy"),
        "p_yes": first.get("p_yes"),
        "p_no": first.get("p_no"),
        "p_yes_binary": first.get("p_yes_binary"),
        "matched_yes_tokens": first.get("matched_yes_tokens") or [],
        "matched_no_tokens": first.get("matched_no_tokens") or [],
        "branch_mass": first.get("branch_mass"),
        "top_logprobs": first.get("top_logprobs") or [],
        "decision_position": first.get("decision_position"),
        "skipped_prefix": first.get("skipped_prefix") or [],
        "skipped_len": first.get("skipped_len"),
        "per_position_top_k": first.get("per_position_top_k") or [],
        "control_tokens": first.get("control_tokens") or [],
        "no_substantive_position": bool(first.get("no_substantive_position")),
        "lp_buy_sum": None,
        "lp_nobuy_sum": None,
        "lp_buy_tokens": None,
        "lp_nobuy_tokens": None,
        "raw_logprob_response": first.get("raw_logprob_response", ""),
        "neither_branch_in_top_k": bool(first.get("neither_branch")),
        "raw_content": first.get("raw_content", ""),
        "p_buy_normalized": None,
        "succeeded": bool(first.get("succeeded")),
    }


def make_first_token_scorer(
    base_url: str,
    model: str,
    timeout: float = 120.0,
    *,
    post: PostFn = _post_json,
    labels: tuple[str, str] = DEFAULT_LABELS,
    scan_tokens: int = 1,
    control_tokens: tuple[str, ...] = (),
) -> Callable[[list[dict[str, Any]]], dict[str, Any]]:
    """Build the default one-call-per-prompt logprob scorer.

    The returned function takes the chat messages and returns the unified
    logprob result (p_buy_logprob/p_yes, p_nobuy_logprob/p_no,
    branch_mass, the matched token forms, the raw top-k list and the
    neither-branch flag). labels names the two answer branches the tokens
    are matched against ("yes"/"no" for the R1-YESNO profile).
    scan_tokens is the decision-scan window (the request's max_tokens; 1
    keeps the historical single-token call, a larger window lets the
    parser walk past control/channel tokens). control_tokens extends the
    control-token spec with exact per-model token strings.
    """
    if scan_tokens < 1:
        raise ValueError(f"scan_tokens must be >= 1, got {scan_tokens}")
    root = _server_root(base_url)

    def scorer(messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = _first_token_payload(model, messages, scan_tokens)
        try:
            status, body = post(f"{root}/v1/chat/completions", payload, timeout)
        except OSError as exc:  # surfaced, never swallowed
            return {
                **_unified({"succeeded": False, "raw_logprob_response": str(exc)}),
            }
        parsed = parse_first_token_response(body, labels, control_tokens)
        if status != 200:
            parsed["succeeded"] = False
        return _unified(parsed)

    return scorer


def make_candidate_scorer(
    base_url: str,
    model: str,
    timeout: float = 120.0,
    *,
    post: PostFn = _post_json,
    label_order: tuple[str, str] | None = None,
) -> Callable[[list[dict[str, Any]]], dict[str, Any]]:
    """Build the teacher-forced two-calls-per-prompt candidate scorer.

    Each call appends one candidate to the chat-templated prompt and reads
    the candidate's own token logprobs; a softmax over the two sums gives
    p_buy/p_nobuy (and a length-normalized variant). The candidate order
    is `label_order` (default: the forward A/B order), and every result
    stamps the `label_order` it actually scored. The raw responses are
    concatenated and truncated for audit.
    """
    root = _server_root(base_url)
    order = tuple(label_order) if label_order else AB_LABEL_ORDERS[0]

    def scorer(messages: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = render_chat_template(messages)
        raw_parts: list[str] = []
        sums: dict[str, dict[str, Any]] = {}
        ok = True
        for candidate in order:
            payload = _candidate_payload(model, prompt + candidate)
            try:
                status, body = post(f"{root}/completions", payload, timeout)
            except OSError as exc:  # surfaced, never swallowed
                raw_parts.append(str(exc))
                sums[candidate] = {"lp_sum": None, "lp_tokens": 0, "lp_mean": None}
                ok = False
                continue
            parsed = parse_candidate_response(body)
            raw_parts.append(parsed["raw_logprob_response"])
            summed = sum_candidate_logprobs(
                parsed["token_logprobs"], count_candidate_tokens(candidate)
            )
            if status != 200 or not parsed["succeeded"] or summed["lp_sum"] is None:
                ok = False
            sums[candidate] = summed
        buy = sums[_PURCHASE_CANDIDATE]
        nobuy = sums[_NOBUY_CANDIDATE]
        soft = candidate_softmax(buy["lp_sum"], nobuy["lp_sum"])
        soft_normalized = candidate_softmax(buy["lp_mean"], nobuy["lp_mean"])
        branch_mass = (
            soft["p_buy"] + soft["p_nobuy"]
            if soft["p_buy"] is not None and soft["p_nobuy"] is not None
            else None
        )
        return {
            "logprob_mode": CANDIDATE_SCORING,
            "label_order": order,
            "p_buy_logprob": soft["p_buy"],
            "p_nobuy_logprob": soft["p_nobuy"],
            "branch_mass": branch_mass,
            "top_logprobs": [],
            "lp_buy_sum": buy["lp_sum"],
            "lp_nobuy_sum": nobuy["lp_sum"],
            "lp_buy_tokens": buy["lp_tokens"],
            "lp_nobuy_tokens": nobuy["lp_tokens"],
            "raw_logprob_response": _truncate(" || ".join(raw_parts)),
            "neither_branch_in_top_k": False,
            "raw_content": "",
            "p_buy_normalized": soft_normalized["p_buy"],
            "succeeded": ok,
        }

    return scorer


def make_ab_scorer(
    base_url: str,
    model: str,
    timeout: float = 120.0,
    *,
    post: PostFn = _post_json,
) -> Callable[[list[dict[str, Any]]], dict[str, Any]]:
    """Build the A/B executor: both label orders per prompt, ONE result.

    For every prompt the executor runs the candidate scorer twice - once
    per AB_LABEL_ORDERS order ("purchase" asked first, then the reversal)
    - and merges the two passes into one result. The merged p(buy) is
    average_ab_p_buy of the two orders (a label-position bias averages out
    instead of skewing the cell); each order's raw result is kept under
    its own label_order stamp in ab_results. A cell succeeds only when
    BOTH order halves succeeded - a broken half fails the cell, so a
    one-order average can never be stored silently.
    """
    order_scorers = [
        make_candidate_scorer(base_url, model, timeout, post=post, label_order=order)
        for order in AB_LABEL_ORDERS
    ]

    def scorer(messages: list[dict[str, Any]]) -> dict[str, Any]:
        ab_results = [order_scorer(messages) for order_scorer in order_scorers]
        succeeded = all(bool(result.get("succeeded")) for result in ab_results)
        forward, reversed_ = ab_results[0], ab_results[1]
        p_buy = p_nobuy = p_buy_normalized = None
        if succeeded:
            p_buy = average_ab_p_buy(
                forward["p_buy_logprob"], reversed_["p_buy_logprob"]
            )
            p_nobuy = average_ab_p_buy(
                forward["p_nobuy_logprob"], reversed_["p_nobuy_logprob"]
            )
            p_buy_normalized = average_ab_p_buy(
                forward["p_buy_normalized"], reversed_["p_buy_normalized"]
            )
        raw = " || ".join(
            str(result.get("raw_logprob_response") or "") for result in ab_results
        )
        return {
            "logprob_mode": CANDIDATE_SCORING,
            "ab_orders": True,
            "p_buy_logprob": p_buy,
            "p_nobuy_logprob": p_nobuy,
            "branch_mass": (
                p_buy + p_nobuy if p_buy is not None and p_nobuy is not None else None
            ),
            # Per-order raw logprob sums live inside ab_results; the merged
            # cell stores no single-order measurement at the top level.
            "top_logprobs": [],
            "lp_buy_sum": None,
            "lp_nobuy_sum": None,
            "lp_buy_tokens": None,
            "lp_nobuy_tokens": None,
            "raw_logprob_response": _truncate(raw),
            "neither_branch_in_top_k": False,
            "raw_content": "",
            "p_buy_normalized": p_buy_normalized,
            "ab_results": ab_results,
            "succeeded": succeeded,
        }

    return scorer


def make_scorer(
    mode: str,
    base_url: str,
    model: str,
    timeout: float = 120.0,
    *,
    post: PostFn = _post_json,
    ab_orders: bool = False,
    labels: tuple[str, str] = DEFAULT_LABELS,
    scan_tokens: int = SCAN_TOKENS,
    control_tokens: tuple[str, ...] = (),
) -> Callable[[list[dict[str, Any]]], dict[str, Any]]:
    """Pick the scorer for one --logprob-mode; unknown modes refuse loudly.

    With ab_orders=True (candidate_scoring only) the scorer becomes the
    A/B executor: every prompt is scored with BOTH label orders and the
    two halves are merged into one averaged result. first_token has no
    A/B form, so that combination refuses loudly instead of silently
    scoring one order. labels threads the answer words (from the run's
    response_format) into the first_token branch matcher. scan_tokens is
    the first_token decision-scan window (the request's max_tokens; the
    production default of 8 walks past control-token prefixes) and
    control_tokens extends the control-token spec per model - both only
    apply to first_token (candidate_scoring generates no tokens).
    """
    if mode == FIRST_TOKEN:
        if ab_orders:
            raise ValueError(
                "ab_orders=True requires candidate_scoring "
                f"(no A/B form for {FIRST_TOKEN!r})"
            )
        return make_first_token_scorer(
            base_url,
            model,
            timeout,
            post=post,
            labels=labels,
            scan_tokens=scan_tokens,
            control_tokens=control_tokens,
        )
    if mode == CANDIDATE_SCORING:
        if ab_orders:
            return make_ab_scorer(base_url, model, timeout, post=post)
        return make_candidate_scorer(base_url, model, timeout, post=post)
    raise ValueError(
        f"unknown logprob mode {mode!r} (choose from {', '.join(LOGP_MODES)})"
    )

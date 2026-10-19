"""Recognition probes for the three-game experiment.

A recognition probe asks the model, in a completely separate session
(fresh API call, no decision transcript included), whether it recognises
the task and what it knows about how people play it.  Probes are asked
at the canonical rung and one perturbed rung, and every probe record
goes to its own JSONL namespace so it can never contaminate the main
decision data.

- ``probe_prompt`` builds the probe prompt for one game and rung.
- ``code_recognition`` codes a probe answer: RECOGNISING when the model
  names the paradigm or cites human-data facts, NOT_RECOGNISING
  otherwise, UNKNOWN when the answer is empty.
"""

from __future__ import annotations

# Probes are single-shot: exactly one draw per (rung, arm, model, persona).
PROBE_DRAWS_PER_PERSONA = 1

_PROBE_STEM = (
    "Do you recognise this task? If you do, name it, and state what is "
    "known about how people play it."
)

#: A minimal description of each probe rung so the model has something
#: to recognise (the probe never includes any decision transcript).
_RUNG_DESCRIPTIONS: dict[str, str] = {
    "r11-20": (
        "a game where two players each request an integer amount of money "
        "between 11 and 20 shekels, each keeps the request, and a player "
        "gets 20 extra shekels for requesting exactly one shekel less than "
        "the other player"
    ),
    "r31-40": (
        "a game where two players each request an integer amount of money "
        "between 31 and 40 shekels, each keeps the request, and a player "
        "gets 20 extra shekels for requesting exactly one shekel less than "
        "the other player"
    ),
    "private": (
        "a task where you privately roll a six-sided die and are paid per "
        "pip of the number you report, with the roll never revealed"
    ),
    "public": (
        "a task where you privately roll a six-sided die and your reported "
        "number is publicly announced, with the roll never revealed"
    ),
    "G1": (
        "a 3x3 simultaneous-move matrix game with actions A1, A2 and J, "
        "where each cell pays (Row, Column) and the J-vs-J cell is the "
        "only one where both players earn the high payoff"
    ),
    "G4": (
        "a 3x3 simultaneous-move matrix game with actions A1, A2 and J, "
        "where the top-left cell pays Row 20 instead of 10"
    ),
}

#: Phrases (lowercased) that count as naming the paradigm or citing
#: human benchmark facts; the codebook's binary RECOGNISING coding.
_RECOGNITION_MARKERS = (
    "11-20",
    "11 to 20",
    "arad",
    "rubinstein",
    "beauty contest",
    "traveler",
    "traveller",
    "die roll",
    "die-roll",
    "lying game",
    "ostermaier",
    "abeler",
    "joker game",
    "joker",
    "level-k",
    "level k",
    "matrix game",
    "focal point",
    "people typically",
    "humans typically",
    "experimental economics",
    "most people",
)


def probe_prompt(
    game: str, variant: str, username: str, persona_text: str | None
) -> str:
    """The full probe prompt: persona section, rung description, question."""
    if (game, variant) not in _RUNG_DESCRIPTIONS and variant not in (
        "r11-20",
        "r31-40",
        "private",
        "public",
        "G1",
        "G4",
    ):
        raise ValueError(f"unknown probe rung: {game}/{variant}")
    description = _RUNG_DESCRIPTIONS.get(variant)
    if description is None:  # pragma: no cover - table and keys stay in sync
        raise ValueError(f"no probe description for {game}/{variant}")
    persona_section = (
        f"=== EMBODY THIS PERSON ===\nYou are {username}."
        if persona_text is None
        else f"=== EMBODY THIS PERSON ===\n{persona_text}"
    )
    return (
        f"{persona_section}\n"
        "=== SECTION 2: SCENARIO ===\n\n"
        f"## Scenario\nConsider the following task: {description}.\n"
        "=== SECTION 3: QUESTION ===\n\n"
        f"## Question\n{_PROBE_STEM}\n"
        "=== SECTION 4: CONTEXT ===\n\n"
        "## Context\nAnswer from your own knowledge. This is a single "
        "question, not a decision in the task.\n"
        "=== SECTION 5: JSON OUTPUT REQUIREMENT ===\n"
        "## Your Response\n"
        "Respond with ONLY JSON containing two fields, in this order:\n"
        '{"recognised": <true or false>, '
        '"answer": "name the task and what is known about how people play it"}'
    )


def code_recognition(raw_content: str | None) -> str:
    """Binary RECOGNISING coding of one probe answer (see module docstring)."""
    if not raw_content:
        return "UNKNOWN"
    text = raw_content.lower()
    if not text.strip():
        return "UNKNOWN"
    return (
        "RECOGNISING"
        if any(marker in text for marker in _RECOGNITION_MARKERS)
        else "NOT_RECOGNISING"
    )

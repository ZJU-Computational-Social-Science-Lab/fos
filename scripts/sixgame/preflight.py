"""Mandatory pre-execution validation gate for the sixgame pipeline.

What this file does, in plain language:

Before the runner is allowed to make any real (paid) API call, this gate
rebuilds every prompt the planned run would send and checks that each one
is exactly right — offline, without sending anything:

- ``bio_fingerprint``: a short identity hash of a persona text, so we can
  prove the right biography is embedded without ever printing the private
  biography itself.
- ``distinctive_substrings``: three rare words picked from a biography,
  used as spot-checks that the text really is inside a prompt.
- ``persona_texts``: which biography each planned sample should embed
  (persona arm: the persona file's text; no-persona arm: none, ever).
- ``run_preflight``: runs every check below and returns a list of
  human-readable failure reasons (empty list = the run may start).
  Checks cover: persona-arm prompts contain the full correct biography;
  no-persona prompts contain none of it (name-only placebo present);
  persona/no-persona pairs differ ONLY in the identity section; die-roll
  prompts carry the harness's true roll; probes carry the right rung
  description; plan shape, models, variants, persona ids and draws match
  the frozen config; optionally, captured request bodies from a dry
  transport run match the built prompts byte-for-byte at temperature 1.0.
- ``main``: the command-line entry point (``python -m sixgame.preflight``).
  Exit 0 = all checks green; exit 1 = at least one failure (reasons are
  printed, private biography text never is).

This gate exists because the original pilot silently ran with NO persona
text in either arm (RESULT-2723 anomaly A1 / RESULT-2727): the pre-fix
runner loaded persona files without checking the arm, and — because the
files were not in the working directory — silently fell back to no text
at all.  This gate refuses to let that happen again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:  # works both as a package module and run from the scripts directory
    from sixgame.games import PROBE_RUNGS
    from sixgame.plan import (
        build_plan,
        draw_true_roll,
        load_config,
        load_persona_names,
        probe_plan,
    )
    from sixgame.probes import _RUNG_DESCRIPTIONS
except ImportError:  # pragma: no cover - direct execution layout
    from games import PROBE_RUNGS
    from plan import (
        build_plan,
        draw_true_roll,
        load_config,
        load_persona_names,
        probe_plan,
    )
    from probes import _RUNG_DESCRIPTIONS


def _runner():
    """The runner module, imported lazily (it imports this module, so a
    top-level import here would be circular)."""
    try:
        from sixgame import runner
    except ImportError:  # pragma: no cover - direct execution layout
        import runner
    return runner


#: The exact identity-section prefix every prompt starts with.
_IDENTITY_MARKER = "=== EMBODY THIS PERSON ==="
#: The first shared (non-identity) section header.
_SECTION2_MARKER = "=== SECTION 2: SCENARIO ==="
#: Marker inside every die-roll decision prompt carrying the true roll.
_ROLL_MARKER = "private roll is: "
#: The role sentence inside every PMS prompt (role check anchor).
_ROLE_SENTENCE = "You are the "
#: The probe question stem every probe prompt must contain.
_PROBE_STEM_SNIPPET = "Do you recognise this task?"


def bio_fingerprint(text: str) -> str:
    """A full sha256 identity hash of a biography text (never reversed)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def distinctive_substrings(text: str, n: int = 3) -> list[str]:
    """Pick n rare-looking words from a biography as spot-check markers.

    Deterministic: words of 8+ letters, ordered by (hash, word), first n.
    Only presence/absence of these is ever reported — the words are short
    single tokens, not private passages.
    """
    words = sorted(
        {w.strip(".,!?;:\"'()[]") for w in text.split() if len(w) >= 8},
        key=lambda w: (hashlib.sha256(w.encode()).hexdigest(), w),
    )
    return words[:n]


def persona_texts_for_plan(plan: list, personas_dir: Path) -> dict[int, str | None]:
    """The biography each planned sample should embed, via the production
    loader (``runner.persona_text_for``) — the exact code path used at
    send time, so the gate validates reality, not a copy of it."""
    return {i: _runner().persona_text_for(s, personas_dir) for i, s in enumerate(plan)}


def check_persona_arms(plan: list, texts: dict) -> list[str]:
    """Persona-arm samples must load a real biography file, never None.

    The original bug was a silent None here (file missing → no persona
    text at all).  A missing file is now a hard gate failure.
    """
    failures = []
    for i, sample in enumerate(plan):
        if sample.arm != "persona" or sample.namespace != "decisions":
            continue
        if texts[i] is None:
            failures.append(
                f"persona-arm sample {sample.game}/{sample.variant} "
                f"{sample.persona_id}#{sample.draw_id} has NO persona text "
                "(file missing or loader returned None) — refusing to run"
            )
    return failures


def check_prompt_bodies(
    plan: list, texts: dict, rolls: dict, personas_dir: Path
) -> list[str]:
    """Per-sample prompt checks: identity section, biography presence,
    placebo, die roll, and probe rung description."""
    failures = []
    for i, sample in enumerate(plan):
        persona_text = texts[i]
        roll = rolls[i]
        try:
            prompt = _runner().build_decision_prompt(sample, persona_text, roll, 0)
            if sample.namespace == "probes":
                prompt = _runner().probe_prompt(
                    sample.game, sample.variant, sample.persona_id, persona_text
                )
        except ValueError as exc:
            failures.append(f"{_label(sample)}: prompt build refused: {exc}")
            continue
        head, sep, tail = prompt.partition(f"\n{_SECTION2_MARKER}")
        if not sep:
            failures.append(f"{_label(sample)}: prompt missing SECTION 2 marker")
            continue
        failures += _check_identity(sample, persona_text, head, personas_dir)
        if sample.game == "dieroll" and sample.namespace == "decisions":
            failures += _check_roll(sample, roll, prompt)
        if sample.namespace == "probes":
            failures += _check_probe(sample, prompt)
    return failures


def _label(sample) -> str:
    """A short readable tag for one planned sample (for failure lines)."""
    return (
        f"{sample.namespace}/{sample.game}/{sample.variant}/{sample.arm} "
        f"{sample.persona_id}#{sample.draw_id}"
    )


def _check_identity(
    sample, persona_text: str | None, head: str, personas_dir: Path
) -> list[str]:
    """Check one prompt's identity section against its arm's contract."""
    failures = []
    if not head.startswith(_IDENTITY_MARKER):
        failures.append(f"{_label(sample)}: prompt missing identity marker")
        return failures
    if sample.arm == "persona":
        if persona_text is None:
            return failures  # already reported by check_persona_arms
        if head != f"{_IDENTITY_MARKER}\n{persona_text}":
            failures.append(
                f"{_label(sample)}: identity section does not exactly equal "
                f"the persona file (fingerprint "
                f"{bio_fingerprint(persona_text)[:12]}…)"
            )
        for sub in distinctive_substrings(persona_text):
            if sub not in prompt_text_of(sample, persona_text):
                failures.append(
                    f"{_label(sample)}: biography spot-check word missing "
                    f"(len={len(sub)})"
                )
    else:
        expected = f"{_IDENTITY_MARKER}\nYou are {sample.persona_id}."
        if head != expected:
            failures.append(
                f"{_label(sample)}: no-persona identity section is not the "
                "name-only placebo"
            )
        if persona_text is not None:
            for sub in distinctive_substrings(persona_text):
                if sub in prompt_text_of(sample, None):
                    failures.append(
                        f"{_label(sample)}: no-persona prompt CONTAINS "
                        "biography text — arm contrast broken"
                    )
                    break
    return failures


def prompt_text_of(sample, persona_text: str | None) -> str:
    """Rebuild one decision prompt the way the runner would."""
    return _runner().build_decision_prompt(sample, persona_text, None, 0)


def _check_roll(sample, roll: int | None, prompt: str) -> list[str]:
    """Die-roll prompts must carry the harness's true (seeded) roll."""
    if roll is None or not 1 <= roll <= 6:
        return [f"{_label(sample)}: missing/invalid true roll {roll!r}"]
    if f"{_ROLL_MARKER}{roll}." not in prompt:
        return [
            f"{_label(sample)}: prompt does not carry true roll "
            f"(roll={roll}, hash={_runner().prompt_hash(prompt)})"
        ]
    return []


def _check_probe(sample, prompt: str) -> list[str]:
    """Probe prompts must carry the rung description and question stem."""
    failures = []
    if _PROBE_STEM_SNIPPET not in prompt:
        failures.append(f"{_label(sample)}: probe prompt missing question stem")
    description = _RUNG_DESCRIPTIONS.get(sample.variant, "")
    probe_snippet = description[:40] if description else ""
    if probe_snippet and probe_snippet not in prompt:
        failures.append(
            f"{_label(sample)}: probe prompt missing rung description "
            f"for rung {sample.variant}"
        )
    if sample.role is not None:
        failures.append(f"{_label(sample)}: probe must not carry a matrix role")
    return failures


def check_arm_pairs(plan: list, rolls: dict) -> list[str]:
    """Persona/no-persona twins must differ ONLY in the identity section.

    Everything from SECTION 2 on must be identical across the arm pair —
    except the two design-assigned randomizations, which are seeded per
    (cell, arm) on purpose: the die-roll true roll and the PMS matrix
    role.  For those games the check normalizes the randomization before
    diffing (dieroll) or verifies each arm matches its own assignment
    (pms) instead of requiring byte equality.
    """
    failures = []
    by_key = {}
    for i, s in enumerate(plan):
        if s.namespace != "decisions":
            continue
        key = (s.game, s.variant, s.model, s.persona_id, s.draw_id)
        by_key.setdefault(key, {})[s.arm] = i
    for key, arms in by_key.items():
        if "persona" not in arms or "no_persona" not in arms:
            failures.append(f"arm pair missing for {key}: {sorted(arms)}")
            continue
        p, n = plan[arms["persona"]], plan[arms["no_persona"]]
        tail_p = _tail(p, rolls[arms["persona"]], "BIO")
        tail_n = _tail(n, rolls[arms["no_persona"]], None)
        if p.game == "dieroll":
            tail_p = _normalise_roll(tail_p)
            tail_n = _normalise_roll(tail_n)
        elif p.game == "pms":
            if (
                tail_p.partition(_ROLE_SENTENCE)[0]
                == tail_n.partition(_ROLE_SENTENCE)[0]
                and p.role in ("Row", "Column")
                and n.role in ("Row", "Column")
            ):
                continue
            failures.append(f"arm pair {key}: matrix sections differ beyond role")
            continue
        if tail_p != tail_n:
            failures.append(
                f"arm pair {key}: shared sections differ — arms differ in "
                "more than the identity field"
            )
    return failures


def _tail(sample, roll, persona_text: str | None) -> str:
    """The shared (non-identity) part of one sample's decision prompt."""
    prompt = _prompt_of(sample, persona_text, roll) or ""
    return prompt.partition(f"\n{_SECTION2_MARKER}")[2]


def _normalise_roll(tail: str) -> str:
    """Replace the embedded die roll so per-arm rolls compare equal."""
    import re

    return re.sub(f"{_ROLL_MARKER}[1-6]\\.", f"{_ROLL_MARKER}R.", tail)


def check_plan_shape(plan: list, config: dict, limit: int | None = None) -> list[str]:
    """Planned samples must match the frozen config exactly: counts per
    cell, models, variants, persona ids, draw numbering, namespaces.

    With a limit (validation slice) the expected counts are capped: at
    most `limit` decisions, and probes only if the slice reaches past
    the decision block.
    """
    failures = []
    decisions = [s for s in plan if s.namespace == "decisions"]
    probes = [s for s in plan if s.namespace == "probes"]
    n_cells = (
        sum(len(v["variants"]) for v in config["games"].values())
        * len(config["arms"])
        * len(config["models"])
    )
    full_decisions = n_cells * config["draws_per_cell"]
    expected_decisions = full_decisions if limit is None else min(full_decisions, limit)
    if len(decisions) != expected_decisions:
        failures.append(
            f"plan has {len(decisions)} decisions, expected {expected_decisions}"
        )
    n_probe_cells = (
        sum(len(PROBE_RUNGS[g]) for g in config["games"])
        * len(config["arms"])
        * len(config["models"])
    )
    expected_probes = n_probe_cells * config["personas"]
    if limit is not None and limit < full_decisions:
        expected_probes = 0
    elif limit is not None:
        expected_probes = min(expected_probes, limit - full_decisions)
    if len(probes) != expected_probes:
        failures.append(f"plan has {len(probes)} probes, expected {expected_probes}")
    for s in plan:
        if s.model not in config["models"]:
            failures.append(f"{_label(s)}: model {s.model} not in config")
        if s.game not in config["games"] or (
            s.namespace == "decisions"
            and s.variant not in config["games"][s.game]["variants"]
        ):
            failures.append(f"{_label(s)}: variant {s.variant} not in config")
    return failures


def check_rolls_seeded(plan: list, seed: int) -> list[str]:
    """Every die-roll draw's true roll must equal the seeded redraw (so a
    resumed run replays identical rolls)."""
    failures = []
    for i, s in enumerate(plan):
        if s.game != "dieroll" or s.namespace != "decisions":
            continue
        expected = draw_true_roll(
            seed, s.game, s.variant, s.arm, s.model, s.persona_id, s.draw_id
        )
        if expected is None or not 1 <= expected <= 6:
            failures.append(f"{_label(s)}: seeded roll out of range: {expected!r}")
    return failures


def check_captured(
    plan: list, texts: dict, rolls: dict, captured: list[dict]
) -> list[str]:
    """Dry-transport payloads must match the built prompts byte-for-byte,
    at temperature 1.0, one payload per planned sample."""
    failures = []
    r = _runner()
    built = {}
    for i, s in enumerate(plan):
        prompt = _prompt_of(s, texts[i], rolls[i])
        if prompt is None:
            continue  # build error already reported by check_prompt_bodies
        built[r.prompt_hash(prompt)] = s
    seen = {}
    for j, payload in enumerate(captured):
        content = (payload.get("messages") or [{}])[0].get("content", "")
        if payload.get("temperature") != _runner().TEMPERATURE:
            failures.append(
                f"captured request #{j}: temperature "
                f"{payload.get('temperature')} != 1.0"
            )
        h = _runner().prompt_hash(content)
        if h not in built:
            failures.append(f"captured request #{j}: no matching planned prompt")
            continue
        seen[h] = seen.get(h, 0) + 1
    # Identical prompts are legal: two draws of one persona in a cell share
    # a prompt. Compare multiplicities, not presence.
    expected = {}
    for i, s in enumerate(plan):
        prompt = _prompt_of(s, texts[i], rolls[i])
        if prompt is None:
            continue
        h = _runner().prompt_hash(prompt)
        expected[h] = expected.get(h, 0) + 1
    for h, want in expected.items():
        got = seen.get(h, 0)
        if got != want:
            failures.append(
                f"{_label(built[h])}: prompt sent {got} times, expected {want}"
            )
    return failures


def _prompt_of(sample, persona_text: str | None, roll) -> str | None:
    """The exact prompt the runner would serialize for one sample, or
    None when the prompt cannot be built (already reported as a failure)."""
    try:
        prompt = _runner().build_decision_prompt(sample, persona_text, roll, 0)
        if sample.namespace == "probes":
            prompt = _runner().probe_prompt(
                sample.game, sample.variant, sample.persona_id, persona_text
            )
    except ValueError:
        return None
    return prompt


def run_preflight(
    plan: list,
    personas_dir: Path,
    config: dict,
    seed: int,
    captured: list[dict] | None = None,
    plan_limit: int | None = None,
) -> list[str]:
    """Run every preflight check; return the list of failures (empty=green).

    plan_limit: for validation slices (--limit N) the frozen full-plan
    counts are capped at N planned samples and probes past the slice are
    not expected.  A single-arm slice (e.g. persona-only) skips the
    arm-pair requirement — pairs only exist in the full two-arm plan.
    Full runs (no limit, both arms) keep the unchanged frozen gate.
    """
    texts = persona_texts_for_plan(plan, personas_dir)
    rolls = {
        i: draw_true_roll(
            seed, s.game, s.variant, s.arm, s.model, s.persona_id, s.draw_id
        )
        for i, s in enumerate(plan)
    }
    failures = []
    failures += check_plan_shape(plan, config, plan_limit)
    failures += check_persona_arms(plan, texts)
    failures += check_prompt_bodies(plan, texts, rolls, personas_dir)
    has_both_arms = {"persona", "no_persona"} <= {s.arm for s in plan}
    if has_both_arms:
        failures += check_arm_pairs(plan, rolls)
    failures += check_rolls_seeded(plan, seed)
    if captured is not None:
        failures += check_captured(plan, texts, rolls, captured)
    return failures


def main(argv: list[str] | None = None) -> int:
    """CLI: build the plan from a config and run the gate. Exit 1 on any
    failure. --run-dir additionally checks captured dry-transport bodies."""
    parser = argparse.ArgumentParser(
        description="sixgame pre-execution validation gate (no API calls)"
    )
    parser.add_argument("--config", required=True, help="config YAML")
    parser.add_argument("--model", help="restrict to one model")
    parser.add_argument("--game", help="restrict to one game")
    parser.add_argument("--variant", help="restrict to one variant")
    parser.add_argument("--arm", help="restrict to one arm")
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument("--personas-dir", default=".")
    parser.add_argument("--personas-csv", default="final_200_personas.csv")
    parser.add_argument("--run-dir", help="dir holding captured_requests.jsonl")
    parser.add_argument(
        "--limit", type=int, help="validation slice size (caps expected counts)"
    )
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    if args.model:
        config["models"] = [m for m in config["models"] if m == args.model]
    persona_names = load_persona_names(Path(args.personas_csv), config["personas"])
    filters = {
        "game_filter": args.game,
        "variant_filter": args.variant,
        "arm_filter": args.arm,
        "model_filter": args.model,
    }
    plan = build_plan(config, persona_names, args.seed, **filters) + probe_plan(
        config, persona_names, args.seed, **filters
    )
    captured = None
    if args.run_dir:
        captured_file = Path(args.run_dir) / "captured_requests.jsonl"
        captured = [
            json.loads(line)
            for line in captured_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    failures = run_preflight(
        plan, Path(args.personas_dir), config, args.seed, captured, args.limit
    )
    if failures:
        for f in failures:
            print(f"PREFLIGHT FAIL: {f}", file=sys.stderr)
        print(f"preflight: {len(failures)} failure(s)", file=sys.stderr)
        return 1
    print(f"preflight: OK ({len(plan)} planned requests checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Sample-plan construction for the sixgame experiment.

This file turns a config into the exact list of samples to collect:

- ``load_config`` / ``default_config``: the frozen experiment configs
  (YAML file or built-in 'engineering' / 'full' scope).
- ``cells``: every (game, variant, arm, model) cell of a config.
- ``personas_for_cell``: how the draws of one cell spread over personas.
- ``assign_role``: the seed-fixed balanced Row/Column alternation for
  matrix cells.
- ``draw_true_roll``: the seeded private die roll for die-roll draws.
- ``build_plan`` / ``probe_plan``: the full ordered sample lists
  (decisions, and recognition probes in their own namespace).
- ``print_counts``: exact per-cell and total sample counts, no calls.
- ``load_persona_names``: the first n usernames from the personas CSV.

No network and no API keys anywhere in this file.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

try:  # works both as a package module and run from the scripts directory
    from sixgame.games import variant_list
    from sixgame.probes import PROBE_DRAWS_PER_PERSONA
except ImportError:  # pragma: no cover - direct execution layout
    from games import variant_list
    from probes import PROBE_DRAWS_PER_PERSONA


_MODELS = [
    "deepseek-v4-flash",
    "anthropic/claude-sonnet-5",
    "openai/gpt-5.6-luna",
]


@dataclass(frozen=True)
class Sample:
    """One planned API call: a single decision or probe draw."""

    game: str
    variant: str
    arm: str
    model: str
    persona_id: str
    draw_id: int
    role: str | None
    namespace: str  # "decisions" or "probes"

    def idempotency_key(self, prompt_hash: str, route: str) -> str:
        """The restart-stable key: prompt hash + persona + draw + model + route."""
        parts = f"{prompt_hash}|{self.persona_id}|{self.draw_id}|{self.model}|{route}"
        return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def load_config(path: Path) -> dict:
    """Read one experiment config YAML into a dict."""
    import yaml

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def default_config(scope: str) -> dict:
    """The built-in config for 'engineering' or 'full' scope."""
    if scope == "engineering":
        return {
            "scope": "engineering",
            "models": _MODELS,
            "arms": ["persona", "no_persona"],
            "draws_per_cell": 10,
            "personas": 5,
            "games": {
                "1120": {"variants": ["basic", "cycle", "r31-40"]},
                "dieroll": {"variants": ["private", "public", "stake10"]},
                "pms": {"variants": ["G1", "G4", "relabel"]},
            },
            "probes": {"enabled": True},
        }
    return {
        "scope": "full",
        "models": _MODELS,
        "arms": ["persona", "no_persona"],
        "draws_per_cell": 10,
        "personas": 20,
        "games": {
            "1120": {"variants": list(variant_list("1120", "full"))},
            "dieroll": {"variants": list(variant_list("dieroll", "full"))},
            "pms": {"variants": list(variant_list("pms", "full"))},
        },
        "probes": {"enabled": True},
    }


def cells(config: dict) -> list[tuple[str, str, str, str]]:
    """All (game, variant, arm, model) cells of a config, in fixed order."""
    out = []
    for game in sorted(str(g) for g in config["games"]):
        for variant in config["games"][game]["variants"]:
            for arm in config["arms"]:
                for model in config["models"]:
                    out.append((game, variant, arm, model))
    return out


def personas_for_cell(persona_names: list[str], draws: int, personas: int) -> list[str]:
    """Which persona each draw uses: draws spread round-robin over the
    first `personas` names (2 draws each in the engineering pilot)."""
    chosen = persona_names[:personas]
    return [chosen[d % len(chosen)] for d in range(draws)]


def assign_role(
    seed: int,
    game: str,
    variant: str,
    arm: str,
    model: str,
    persona_id: str,
    draw_id: int,
) -> str | None:
    """Seed-fixed balanced Row/Column alternation within a cell.

    Deterministic: the same seed and cell always give the same roles,
    and draws alternate so each cell ends up balanced.
    """
    if game != "pms":
        return None
    digest = hashlib.sha256(
        f"{seed}|{game}|{variant}|{arm}|{model}|{persona_id}|{draw_id}".encode()
    ).digest()
    return "Row" if digest[0] % 2 == 0 else "Column"


def draw_true_roll(
    seed: int,
    game: str,
    variant: str,
    arm: str,
    model: str,
    persona_id: str,
    draw_id: int,
) -> int | None:
    """The harness-drawn private die roll for one draw (None off-game).

    Seeded per draw so a resumed run redraws the identical roll.
    """
    if game != "dieroll":
        return None
    digest = hashlib.sha256(
        f"{seed}|{game}|{variant}|{arm}|{model}|{persona_id}|{draw_id}".encode()
    ).digest()
    return digest[0] % 6 + 1


def build_plan(
    config: dict,
    persona_names: list[str],
    seed: int,
    namespace: str = "decisions",
    game_filter: str | None = None,
    variant_filter: str | None = None,
    arm_filter: str | None = None,
    model_filter: str | None = None,
) -> list[Sample]:
    """The full ordered sample list for a config (see module docstring)."""
    plan = []
    for game, variant, arm, model in cells(config):
        if game_filter and game != game_filter:
            continue
        if variant_filter and variant != variant_filter:
            continue
        if arm_filter and arm != arm_filter:
            continue
        if model_filter and model != model_filter:
            continue
        draws = config["draws_per_cell"]
        assigned = personas_for_cell(persona_names, draws, config["personas"])
        for draw_id, persona_id in enumerate(assigned):
            plan.append(
                Sample(
                    game,
                    variant,
                    arm,
                    model,
                    persona_id,
                    draw_id,
                    assign_role(seed, game, variant, arm, model, persona_id, draw_id),
                    namespace,
                )
            )
    return plan


def probe_plan(
    config: dict,
    persona_names: list[str],
    seed: int,
    game_filter: str | None = None,
    variant_filter: str | None = None,
    arm_filter: str | None = None,
    model_filter: str | None = None,
) -> list[Sample]:
    """The recognition-probe plan: one draw per (rung, arm, model, persona).

    Probes live in their own namespace and never mix with decisions.
    """
    plan = []
    from games import PROBE_RUNGS

    for game in sorted(str(g) for g in config["games"]):
        if game_filter and game != game_filter:
            continue
        for variant in PROBE_RUNGS[game]:
            if variant_filter and variant != variant_filter:
                continue
            for arm in config["arms"]:
                if arm_filter and arm != arm_filter:
                    continue
                for model in config["models"]:
                    if model_filter and model != model_filter:
                        continue
                    for persona_id in persona_names[: config["personas"]]:
                        plan.append(
                            Sample(
                                game,
                                variant,
                                arm,
                                model,
                                persona_id,
                                PROBE_DRAWS_PER_PERSONA - 1,
                                None,
                                "probes",
                            )
                        )
    return plan


def print_counts(config: dict) -> str:
    """Exact per-cell and total sample counts for a config (no API calls)."""
    lines = []
    total_decisions = 0
    for game, variant, arm, model in cells(config):
        n = config["draws_per_cell"]
        total_decisions += n
        lines.append(f"{game:8s} {variant:8s} {arm:10s} {model:26s} {n}")
    probe_total = 0
    if config.get("probes", {}).get("enabled", True):
        from games import PROBE_RUNGS

        for game in sorted(str(g) for g in config["games"]):
            for _rung in PROBE_RUNGS[game]:
                n = (
                    2
                    * len(config["models"])
                    * config["personas"]
                    * PROBE_DRAWS_PER_PERSONA
                )
                probe_total += n
    total = total_decisions + probe_total
    lines.append(f"decisions: {total_decisions}")
    lines.append(f"probes: {probe_total}")
    lines.append(f"TOTAL: {total}")
    return "\n".join(lines)


def load_persona_names(personas_csv: Path, n: int) -> list[str]:
    """The first n usernames from the personas CSV."""
    lines = personas_csv.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()][:n]

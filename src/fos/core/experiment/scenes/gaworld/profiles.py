"""This file defines GAWorld agent profile data and helper functions.
Each function does one simple job:
- GAWorldAgentProfile stores one agent's profile values.
- load_profiles reads a JSON file and turns rows into profile objects.
- profiles_to_fos_agents turns profile objects into FOS agent dictionaries.
- export_profiles_csv writes selected profile fields to a CSV file.

hangzhou_50.json was converted from GAWorld source data on 2026-05-25. Re-run conversion if GAWorld agent data is updated upstream.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class GAWorldAgentProfile:
    """Stores one GAWorld agent profile with demographic, behavior, and state fields."""

    id: str
    name: str
    gender: str
    age: int
    hukou: str
    residence: str
    occupation: str
    income: str
    education: str
    personality_traits: str
    daily_routine: str
    social_network: str
    values: str
    policy_sensitivity: float
    platform_dependence: float
    risk_preference: float
    voice_propensity: float
    mobility_intent: float
    emotion: float
    stress: float
    econ_security: float
    city_identity: float


def load_profiles(path: Path | None = None) -> list[GAWorldAgentProfile]:
    """Reads profile JSON and returns profile objects, or an empty list when missing."""

    source_path = path or Path(__file__).with_name("profiles").joinpath("hangzhou_50.json")
    if not source_path.exists():
        return []

    with source_path.open("r", encoding="utf-8") as file_obj:
        rows = json.load(file_obj)

    return [GAWorldAgentProfile(**row) for row in rows]


def profiles_to_fos_agents(
    profiles: Iterable[GAWorldAgentProfile],
    agent_ids: list[str] | None = None,
) -> list[dict[str, object]]:
    """Converts GAWorld profiles into basic FOS agent dictionaries."""

    generated_agents: list[dict[str, object]] = []
    selected_ids = set(agent_ids) if agent_ids else None

    for profile in profiles:
        if selected_ids and profile.id not in selected_ids:
            continue

        role_prompt = (
            f"Personality: {profile.personality_traits}. "
            f"Daily routine: {profile.daily_routine}. "
            f"Social network: {profile.social_network}. "
            f"Values: {profile.values}."
        )
        generated_agents.append(
            {
                "id": profile.id,
                "name": profile.name,
                "properties": {
                    "occupation": profile.occupation,
                    "income": profile.income,
                    "policy_sensitivity": profile.policy_sensitivity,
                },
                "role_prompt": role_prompt,
                # GAWorld controls its own LLM selection; FOS-side config stays empty.
                "llm_config": {},
            }
        )

    return generated_agents


def export_profiles_csv(profiles: Iterable[GAWorldAgentProfile], output_path: Path) -> None:
    """Writes selected profile fields to a CSV file."""

    fieldnames = [
        "id",
        "name",
        "gender",
        "age",
        "hukou",
        "residence",
        "emotion",
        "stress",
        "econ_security",
        "city_identity",
        "policy_sensitivity",
        "platform_dependence",
        "risk_preference",
        "voice_propensity",
        "mobility_intent",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for profile in profiles:
            row = asdict(profile)
            writer.writerow({name: row[name] for name in fieldnames})

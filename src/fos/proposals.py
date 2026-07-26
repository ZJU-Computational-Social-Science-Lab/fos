# This module loads and validates the Phase 2 proposal registry.
# It provides a frozen Proposal dataclass and functions for loading proposals
# from a JSON data file or looking them up by ID.

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Proposal:
    """A single proposal in the registry, with all its fields frozen."""
    id: str
    short_name: str
    statement: str
    domain: str
    origin: str
    pilot_letter: str | None
    pilot_yes: int | None
    pilot_no: int | None
    pilot_abstain: int | None
    pilot_skip: int | None
    pilot_yes_share: float | None
    notes: str


PROPOSAL_IDS: tuple[str, ...] = (
    "srma",
    "wealth_tax",
    "un_veto",
    "aesthetic_objectivity",
    "meaning_of_life",
    "regifting",
    "shared_workplace",
)

VALID_DOMAINS = frozenset({
    "environmental_policy",
    "economic_policy",
    "institutional_policy",
    "aesthetics",
    "metaphysics",
    "interpersonal_ethics",
    "organisational_norms",
})


def load_proposals(path=None) -> list[Proposal]:
    """Load and validate proposals from JSON. Raise ValueError on failure."""
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "proposals" / "proposals.json"
    with open(path) as f:
        data = json.load(f)

    # Validate schema_version
    if data.get("schema_version") != "1.0.0":
        raise ValueError(f"Expected schema_version 1.0.0, got {data.get('schema_version')}")

    proposals_data = data.get("proposals", [])
    if len(proposals_data) != 7:
        raise ValueError(f"Expected 7 proposals, got {len(proposals_data)}")

    ids = [p["id"] for p in proposals_data]
    if ids != list(PROPOSAL_IDS):
        raise ValueError(f"Proposal IDs must match PROPOSAL_IDS in order. Got: {ids}")

    if len(set(ids)) != 7:
        raise ValueError(f"Duplicate proposal IDs: {ids}")

    proposals = []
    for p in proposals_data:
        if not p.get("statement", "").strip():
            raise ValueError(f"Proposal {p.get('id')} has empty statement")
        if p.get("domain") not in VALID_DOMAINS:
            raise ValueError(f"Proposal {p.get('id')}: invalid domain '{p.get('domain')}'")
        proposals.append(Proposal(
            id=p["id"],
            short_name=p["short_name"],
            statement=p["statement"],
            domain=p["domain"],
            origin=p["origin"],
            pilot_letter=p.get("pilot_letter"),
            pilot_yes=p.get("pilot_yes"),
            pilot_no=p.get("pilot_no"),
            pilot_abstain=p.get("pilot_abstain"),
            pilot_skip=p.get("pilot_skip"),
            pilot_yes_share=p.get("pilot_yes_share"),
            notes=p.get("notes", ""),
        ))

    return proposals


def get_proposal(id: str) -> Proposal:
    """Get a proposal by ID. Raises KeyError with helpful message listing valid IDs."""
    proposals = load_proposals()
    for p in proposals:
        if p.id == id:
            return p
    raise KeyError(f"Unknown proposal id '{id}'. Valid ids: {', '.join(PROPOSAL_IDS)}")

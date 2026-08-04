#!/usr/bin/env python3
"""
Write the population balance table and topic-leakage screen for Phase 3.

This script reads the six population files in data/populations/ and the
proposal registry, then writes two markdown reports:

- balance_table.md: per-population archetype-cell counts (27 cells), Big Five
  trait means/sds, voting-model counts, and a flag for any cell whose count
  differs by more than 2 agents across populations.
- leakage_screen.md: for each of the 600 personas, the content-word overlap
  with each of the 7 proposal statements, plus a list of personas whose bio
  directly references a proposal topic (art/aesthetics, gifts, wealth/tax,
  meaning/purpose, workplace/office, veto/UN, SRMA). Flagged personas are
  reported only — never silently regenerated.

Functions:
- load_populations: read the six population JSON files
- proposal_content_words: content words of a proposal statement (stopwords out)
- bio_words: lowercased content words of one bio
- compute_overlaps: shared content words per persona per proposal
- topic_keywords: per-proposal flag keyword groups
- screen_topic_leakage: find personas that hit a topic keyword group
- build_balance_table: produce the balance_table.md text
- build_leakage_screen: produce the leakage_screen.md text
- main: write both reports
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Ensure the fos package is importable without pip install.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from fos.proposals import load_proposals

OUT_DIR = _REPO_ROOT / "data" / "populations"
PROPOSAL_ORDER = (
    "srma",
    "wealth_tax",
    "un_veto",
    "aesthetic_objectivity",
    "meaning_of_life",
    "regifting",
    "shared_workplace",
)

STOPWORDS = frozenset(
    """
    a an and or of in on to for with by at from as is are be was were been
    has have had do does did not no but if than that this these those it its
    the you your our we they them their he she his her i me my should will
    would can could may might must shall all any both each few more most
    other some such only own same so too very just also about into over
    under up down out off again further once above below between within
    without when where which who whom whose why how what there here then
    whereas rather either neither nor per
    """.split()
)

# Topic keyword groups per proposal, used for the direct-reference flags.
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "aesthetic_objectivity": (
        "art", "arts", "artwork", "artworks", "beauty", "beautiful",
        "aesthetic", "aesthetics", "artist", "artists", "painting",
        "paintings", "sculpture", "music", "taste", "gallery", "museum",
    ),
    "regifting": (
        "gift", "gifts", "giving", "give", "gave", "given", "giver",
        "regift", "regifting", "presents", "present", "gifting",
    ),
    "wealth_tax": (
        "wealth", "wealthy", "tax", "taxes", "taxed", "taxation",
        "asset", "assets", "million", "millionaire", "income", "rich",
        "richness", "net worth",
    ),
    "meaning_of_life": (
        "meaning", "meanings", "meaningful", "meaningless", "purpose",
        "purposes", "meaningfulness", "existential", "meaning-of-life",
    ),
    "shared_workplace": (
        "workplace", "workplaces", "office", "offices", "work", "working",
        "worker", "workers", "employees", "employer", "remote", "hybrid",
        "commute", "coworker", "colleagues", "job", "jobs", "works",
    ),
    "un_veto": (
        "veto", "vetoes", "un", "united nations", "security council",
        "supermajority", "council", "permanent members", "voting rule",
        "veto power",
    ),
    "srma": (
        "stratospheric", "aerosol", "aerosols", "injection", "climate",
        "geoengineering", "solar", "radiation", "sulfur", "sulphur",
        "sulphate", "sulfate", "unep", "united nations environment programme",
        "environmental", "emissions", "mtso",
    ),
}


def _clean_words(text: str) -> list[str]:
    """Lowercase a string and split it into content words (no stopwords)."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def load_populations() -> dict[str, dict]:
    """Read the six population JSON files from data/populations."""
    populations: dict[str, dict] = {}
    for path in sorted(OUT_DIR.glob("pop_*.json")):
        with open(path, encoding="utf-8") as f:
            populations[path.stem] = json.load(f)
    return populations


def proposal_content_words() -> dict[str, set[str]]:
    """Content words (stopwords removed) of each proposal statement."""
    result: dict[str, set[str]] = {}
    for proposal in load_proposals():
        result[proposal.id] = set(_clean_words(proposal.statement))
    return result


def bio_words(bio: str) -> set[str]:
    """Content words of one persona bio."""
    return set(_clean_words(bio))


def compute_overlaps(
    populations: dict[str, dict], content_words: dict[str, set[str]]
) -> dict[str, dict[str, set[str]]]:
    """Shared content words per (population, agent_id) per proposal."""
    result: dict[str, dict[str, set[str]]] = {}
    for pop_id, pop in populations.items():
        result[pop_id] = {}
        for agent in pop["agents"]:
            words = bio_words(agent["bio"])
            agent_id = agent["agent_id"]
            result[pop_id][agent_id] = {}
            for proposal_id, proposal_words in content_words.items():
                shared = words & proposal_words
                if shared:
                    result[pop_id][agent_id][proposal_id] = shared
    return result


def screen_topic_leakage(populations: dict[str, dict]) -> list[dict]:
    """Return flag records for personas whose bio hits a topic keyword group."""
    flags: list[dict] = []
    for pop_id, pop in populations.items():
        for agent in pop["agents"]:
            words = _clean_words(agent["bio"])
            word_set = set(words)
            # multi-word keywords like "united nations" need phrase checks
            bio_lower = agent["bio"].lower()
            for proposal_id, keywords in TOPIC_KEYWORDS.items():
                matched = [
                    kw for kw in keywords
                    if (kw in word_set) or (" " in kw and kw in bio_lower)
                ]
                if matched:
                    flags.append({
                        "population": pop_id,
                        "agent_id": agent["agent_id"],
                        "proposal": proposal_id,
                        "matched": sorted(matched),
                        "bio": agent["bio"],
                    })
    return flags


def _cell_counts(populations: dict[str, dict]) -> dict[str, dict[str, int]]:
    """Per-population counts of each of the 27 archetype cells."""
    counts: dict[str, dict[str, int]] = {}
    for pop_id, pop in populations.items():
        counter: Counter[tuple[str, str, str]] = Counter()
        for agent in pop["agents"]:
            cell = agent["archetype_cell"]
            counter[(cell["age"], cell["political"], cell["sector"])] += 1
        counts[pop_id] = {
            f"{age} | {pol} | {sec}": counter[(age, pol, sec)]
            for age in ("young", "middle", "older")
            for pol in ("liberal", "moderate", "conservative")
            for sec in ("public", "private", "nonprofit")
        }
    return counts


def _big_five_stats(populations: dict[str, dict]) -> dict[str, dict[str, dict[str, float]]]:
    """Per-population mean and sd of each Big Five trait."""
    stats: dict[str, dict[str, dict[str, float]]] = {}
    for pop_id, pop in populations.items():
        stats[pop_id] = {}
        for trait in ("o", "c", "e", "a", "n"):
            values = [agent["big_five"][trait] for agent in pop["agents"]]
            stats[pop_id][trait] = {
                "mean": statistics.mean(values),
                "sd": statistics.pstdev(values),
            }
    return stats


def _voting_model_counts(populations: dict[str, dict]) -> dict[str, Counter[str]]:
    """Per-population count of agents per voting model."""
    counts: dict[str, Counter[str]] = {}
    for pop_id, pop in populations.items():
        counts[pop_id] = Counter(agent["voting_model"] for agent in pop["agents"])
    return counts


def build_balance_table(populations: dict[str, dict]) -> str:
    """Produce the balance_table.md markdown text."""
    cell_counts = _cell_counts(populations)
    trait_stats = _big_five_stats(populations)
    model_counts = _voting_model_counts(populations)
    pop_ids = list(populations.keys())
    trait_names = {"o": "Openness", "c": "Conscientiousness",
                   "e": "Extraversion", "a": "Agreeableness", "n": "Neuroticism"}

    lines: list[str] = []
    lines.append("# Population Balance Table (Phase 3, Step 2)")
    lines.append("")
    lines.append(f"Generated from {len(populations)} populations of "
                 f"{len(next(iter(populations.values()))['agents'])} agents each "
                 f"(27-cell grid: age x political view x work sector).")
    lines.append("")

    # 1. Archetype cell counts
    lines.append("## 1. Archetype cell counts (agents per cell, per population)")
    lines.append("")
    header = ["Cell (age | political | sector)"] + pop_ids + ["max-min", "flag"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for cell in cell_counts[pop_ids[0]]:
        row = [cell]
        values = [cell_counts[pop_id][cell] for pop_id in pop_ids]
        row.extend(str(v) for v in values)
        spread = max(values) - min(values)
        row.append(str(spread))
        row.append("⚠ FLAG" if spread > 2 else "")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("Cells whose count differs by more than 2 agents across "
                 "populations are flagged with ⚠ FLAG.")
    lines.append("")

    # 2. Big Five trait means and sds
    lines.append("## 2. Big Five trait means and standard deviations (per population)")
    lines.append("")
    for trait, label in trait_names.items():
        lines.append(f"### {label} (trait `{trait}`)")
        lines.append("")
        header = ["Population", "mean", "sd"]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "---|" * len(header))
        for pop_id in pop_ids:
            lines.append(f"| {pop_id} | {trait_stats[pop_id][trait]['mean']:.2f} "
                         f"| {trait_stats[pop_id][trait]['sd']:.2f} |")
        lines.append("")

    # 3. Voting model counts
    lines.append("## 3. Voting model counts (per population)")
    lines.append("")
    model_names = list(model_counts[pop_ids[0]].keys())
    header = ["Population"] + [m.split("/")[-1] for m in model_names] + ["total"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for pop_id in pop_ids:
        counts = model_counts[pop_id]
        row = [pop_id] + [str(counts[m]) for m in model_names] + [str(sum(counts.values()))]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_leakage_screen(
    populations: dict[str, dict],
    content_words: dict[str, set[str]],
    overlaps: dict[str, dict[str, dict[str, set[str]]]],
    flags: list[dict],
) -> str:
    """Produce the leakage_screen.md markdown text."""
    lines: list[str] = []
    lines.append("# Topic-Leakage Screen (Phase 3, Step 2)")
    lines.append("")
    lines.append(f"Screened {sum(len(p['agents']) for p in populations.values())} "
                 f"personas against the {len(content_words)} proposal statements.")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("1. **Keyword overlap:** each bio is split into content words "
                 "(lowercased, punctuation stripped, English stopwords removed) "
                 "and compared with the content words of each proposal statement.")
    lines.append("2. **Direct-reference flags:** each bio is checked against a "
                 "topic keyword group per proposal (art/aesthetics, gifts, "
                 "wealth/tax, meaning/purpose, workplace/office, veto/UN, SRMA).")
    lines.append("3. Flagged personas are **reported only** — none were "
                 "regenerated or altered.")
    lines.append("")

    # Proposal content words
    lines.append("## Proposal content words (stopwords removed)")
    lines.append("")
    for proposal_id in PROPOSAL_ORDER:
        words = sorted(content_words[proposal_id])
        lines.append(f"- **{proposal_id}**: {', '.join(words)}")
    lines.append("")

    # Flags
    lines.append("## Flagged personas (direct topic references)")
    lines.append("")
    if not flags:
        lines.append("No personas directly referenced any proposal topic.")
        lines.append("")
    else:
        by_proposal: dict[str, list[dict]] = defaultdict(list)
        for flag in flags:
            by_proposal[flag["proposal"]].append(flag)
        for proposal_id in PROPOSAL_ORDER:
            proposal_flags = by_proposal[proposal_id]
            lines.append(f"### {proposal_id} — {len(proposal_flags)} flag(s)")
            lines.append("")
            if not proposal_flags:
                lines.append("None.")
                lines.append("")
                continue
            lines.append("| population | agent_id | matched keywords | bio |")
            lines.append("|---|---|---|---|")
            for flag in proposal_flags:
                bio = flag["bio"]
                excerpt = bio if len(bio) <= 110 else bio[:107] + "..."
                excerpt = excerpt.replace("|", "\\|")
                lines.append(f"| {flag['population']} | {flag['agent_id']} | "
                             f"{', '.join(flag['matched'])} | {excerpt} |")
            lines.append("")
        lines.append("### Summary counts")
        lines.append("")
        lines.append("| proposal | flagged personas | populations affected |")
        lines.append("|---|---|---|")
        for proposal_id in PROPOSAL_ORDER:
            proposal_flags = by_proposal[proposal_id]
            pops = sorted({f["population"] for f in proposal_flags})
            lines.append(f"| {proposal_id} | {len(proposal_flags)} | {', '.join(pops) or '-'} |")
        lines.append("")

    # Overlap stats
    lines.append("## Keyword overlap with proposal statements (content words)")
    lines.append("")
    lines.append("| proposal | personas with >=1 overlap | max overlap words |")
    lines.append("|---|---|---|")
    for proposal_id in PROPOSAL_ORDER:
        count = 0
        max_overlap = 0
        for pop_overlaps in overlaps.values():
            for agent_overlaps in pop_overlaps.values():
                shared = agent_overlaps.get(proposal_id, set())
                if shared:
                    count += 1
                    max_overlap = max(max_overlap, len(shared))
        lines.append(f"| {proposal_id} | {count} | {max_overlap} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write balance_table.md and leakage_screen.md."""
    populations = load_populations()
    content_words = proposal_content_words()
    overlaps = compute_overlaps(populations, content_words)
    flags = screen_topic_leakage(populations)

    balance = build_balance_table(populations)
    (OUT_DIR / "balance_table.md").write_text(balance, encoding="utf-8")

    leakage = build_leakage_screen(populations, content_words, overlaps, flags)
    (OUT_DIR / "leakage_screen.md").write_text(leakage, encoding="utf-8")

    print(f"[reports] wrote {OUT_DIR / 'balance_table.md'}")
    print(f"[reports] wrote {OUT_DIR / 'leakage_screen.md'}")
    flagged = Counter(f["proposal"] for f in flags)
    print(f"[reports] flagged personas: {len(flags)} total -> {dict(flagged)}")


if __name__ == "__main__":
    main()

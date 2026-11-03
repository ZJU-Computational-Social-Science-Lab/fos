# This module turns the read-only Twin-2K-500 question catalog into the
# restored stimuli entries, in exactly the schema the shipped
# twin2k10_stimuli.json uses, and records a sha256 for every entry so
# nothing can drift. The checked-in generated file must equal a fresh
# extraction — that equality is tested, so the file can never silently
# diverge from the catalog. Functions:
#   extract_from_catalog — the 16 restored stimuli entries, verbatim
#                          from the catalog (never hand-written).
#   entry_sha256         — the stable hash of one stimulus entry.
#   build_manifest       — the provenance document (source paths, sha256
#                          of every entry and of the generated file).
#   write_stimuli_file   — write-once generation of the checked-in file.
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from twin2k10r.stimuli_restored.registry import RESTORED_ARMS

CATALOG_PATH = Path(
    "/home/justin/work/datasets/Twin-2K-500/"
    "question_catalog_and_human_response_csv/question_catalog.json"
)
STIMULI_FILE = Path(__file__).resolve().parent / "data" / "restored_stimuli.json"

# Answer letters the archived prompts used, per option count.
_LETTERS = "ABCDEFGHIJKLMNU"


def _entries_in_survey_order() -> list[tuple[str, str, str]]:
    """(experiment, arm, qid) triples in survey order, arm by arm."""
    triples = []
    for experiment, arms in RESTORED_ARMS.items():
        for arm, qids in arms:
            for qid in qids:
                triples.append((experiment, arm, qid))
    return triples


def extract_from_catalog(catalog_path: Path = CATALOG_PATH) -> list[dict]:
    """The 16 restored stimuli entries, verbatim from the catalog.

    Each entry mirrors the twin2k10_stimuli.json schema: qid, experiment,
    arm, question_text, options (None for the two open-numeric sunk_cost
    questions), question_type, labels, block_name, and the catalog source
    tag. Text and options are copied byte-for-byte — never retyped.
    Raises FileNotFoundError when the catalog is missing.
    """
    with catalog_path.open(encoding="utf-8") as handle:
        catalog = {e["QuestionID"]: e for e in json.load(handle)}
    entries = []
    for experiment, arm, qid in _entries_in_survey_order():
        question = catalog[qid]
        options = question.get("Options")
        n_options = len(options) if options else 0
        entries.append({
            "qid": qid,
            "experiment": experiment,
            "arm": arm,
            "question_text": question["QuestionText"],
            "options": list(options) if options else None,
            "question_type": question["QuestionType"],
            "labels": list(_LETTERS[:n_options]) or None,
            "block_name": question["BlockName"],
            "source": question["source"],
        })
    for entry in entries:
        entry["sha256"] = entry_sha256(entry)
    return entries


def entry_sha256(entry: dict) -> str:
    """The stable hash of one stimulus entry (its content fields only)."""
    payload = json.dumps(
        {k: entry[k] for k in sorted(entry) if k != "sha256"},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_manifest(entries: list[dict], file_path: Path) -> dict:
    """The provenance document for one generated stimuli file."""
    return {
        "generated_from": str(CATALOG_PATH),
        "catalog_sha256": hashlib.sha256(
            CATALOG_PATH.read_bytes()
        ).hexdigest(),
        "n_stimuli": len(entries),
        "entry_sha256": {
            entry["qid"]: entry_sha256(entry) for entry in entries
        },
        "file_sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
    }


def write_stimuli_file(catalog_path: Path = CATALOG_PATH,
                       force: bool = False) -> Path:
    """Generate the checked-in stimuli file (write-once).

    The file is programmatic output of the catalog, never edited by
    hand; a second call refuses to overwrite unless force=True, so an
    accidental rebuild can never replace a verified file quietly.
    """
    if STIMULI_FILE.exists() and not force:
        raise FileExistsError(
            f"{STIMULI_FILE} already exists; pass force=True to regenerate"
        )
    entries = extract_from_catalog(catalog_path)
    STIMULI_FILE.parent.mkdir(parents=True, exist_ok=True)
    STIMULI_FILE.write_text(
        json.dumps(
            {"stimuli": entries}, indent=2, ensure_ascii=False
        ) + "\n",
        encoding="utf-8",
    )
    manifest = build_manifest(entries, STIMULI_FILE)
    manifest_path = STIMULI_FILE.with_name("restored_stimuli_manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return STIMULI_FILE

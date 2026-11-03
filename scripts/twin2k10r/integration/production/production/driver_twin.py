# This file runs one twin-style LEG (one experiment x one blinding, every
# persona x every arm) and makes it resumable: every finished record is
# appended to the leg's records.jsonl the moment it exists, flushed and
# force-synced per record, so a killed run restarts and skips every cell
# already on disk without duplicating anything. A torn tail line (a kill
# mid-write) is truncated before appending — the cell behind it was never
# durable and re-runs. Functions:
#   run_leg — execute or resume one leg; returns (written, total).
from __future__ import annotations

import json
import os
from pathlib import Path

from twin2k10 import cells as frozen_cells
from twin2k10 import registry as frozen_registry
from twin2k10r.integration.production import cells_twin


def leg_dir(run_dir, model: str, experiment: str, blinded: bool) -> Path:
    """One leg's folder: <run>/<model>/<experiment>_<blinding>."""
    blind = "blinded" if blinded else "unblinded"
    return (
        Path(run_dir) / frozen_registry.safe_model_name(model)
        / f"{experiment}_{blind}"
    )


def _repair_torn_tail(path: Path) -> None:
    """Cut a torn final line so the file is valid jsonl again.

    The torn record was never fully written, so its cell re-runs on the
    next pass — this is the durability contract, not data loss.
    """
    if not path.exists():
        return
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        last_newline = raw.rfind(b"\n")
        with path.open("r+b") as handle:
            handle.truncate(last_newline + 1)
            handle.flush()
            os.fsync(handle.fileno())


def run_leg(
    run_dir,
    model: str,
    base_url: str,
    experiment: str,
    blinded: bool,
    personas: list[dict],
    run_id: str,
    dataset_sha256: str,
    spec=None,
    stimuli=None,
    scorers=None,
) -> tuple[int, int]:
    """Execute (or resume) one leg; returns (written, total_on_disk).

    Cells run in pinned order (persona 0-99, then arm in registry order).
    A cell whose five-part identity is already durable is skipped, so a
    resumed run calls the model only for the missing cells.
    """
    from twin2k10r.integration.production import run_plan

    spec = spec or run_plan.twin_specs()[experiment]
    stimuli = stimuli or cells_twin.merged_stimuli()
    blind = "blinded" if blinded else "unblinded"
    directory = leg_dir(run_dir, model, experiment, blinded)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "records.jsonl"
    _repair_torn_tail(path)
    done = frozen_cells.load_existing_keys(path)

    if scorers is None:
        scorer, digit_scorer = cells_twin.make_scorers(model, base_url, stimuli)
    else:
        scorer, digit_scorer = scorers

    written = 0
    planned = 0
    for persona_id in range(len(personas)):
        for arm, _qids in spec.arms:
            planned += 1
            cell = (model, persona_id, experiment, arm, blind)
            if frozen_cells.record_key(cell) in done:
                continue
            record = cells_twin.execute_cell(
                _context(model, base_url, personas, stimuli), spec, stimuli,
                cell, scorer, digit_scorer, run_id, dataset_sha256,
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            written += 1
    return written, planned


def _context(model: str, base_url: str, personas: list[dict], stimuli):
    """The frozen LegContext shape the cell executor reads fields from."""
    from twin2k10 import legexec
    from twin2k10r.integration.production.model_ids import server_model_id

    return legexec.LegContext(
        model=model,
        model_id=server_model_id(model),
        base_url=base_url,
        personas=personas,
        stimuli=stimuli,
        inference=cells_twin.inference_settings(base_url),
    )

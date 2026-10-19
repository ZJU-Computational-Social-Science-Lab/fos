"""Tests that the frozen config manifests produce exactly the planned
sample counts (engineering = 720 = 540 decisions + 180 probes)."""

import yaml
from pathlib import Path

import runner

CONFIGS = Path(__file__).resolve().parents[2] / "scripts" / "sixgame" / "configs"


def _load(name):
    with (CONFIGS / name).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_engineering_config_counts_720_calls():
    config = _load("engineering_pilot.yaml")
    decision_cells = runner.cells(config)
    assert len(decision_cells) == 3 * 3 * 2 * 3  # 27 cells
    decisions = len(decision_cells) * config["draws_per_cell"]
    assert decisions == 540
    # probes: 3 games x 2 rungs x 2 arms x 3 models x 5 personas x 1
    probes = 3 * 2 * 2 * 3 * 5 * 1
    assert probes == 180
    assert decisions + probes == 720
    text = runner.print_counts(config)
    assert "decisions: 540" in text
    assert "probes: 180" in text
    assert "TOTAL: 720" in text


def test_full_pilot_config_counts_are_consistent():
    config = _load("full_pilot.yaml")
    decision_cells = runner.cells(config)
    # every decision cell has exactly the planned draws
    assert all(config["draws_per_cell"] == 10 for _ in decision_cells)
    decisions = len(decision_cells) * 10
    variants_total = 8 + 4 + 3  # 11-20 ladder, die-roll, PMS
    assert len(decision_cells) == variants_total * 2 * 3
    assert decisions == 15 * 2 * 3 * 10  # 900
    probes = 3 * 2 * 2 * 3 * 20 * 1  # 720
    assert decisions + probes == decisions + probes
    text = runner.print_counts(config)
    assert f"decisions: {decisions}" in text
    assert f"probes: {probes}" in text
    assert f"TOTAL: {decisions + probes}" in text


def test_engineering_scope_covers_every_game():
    config = _load("engineering_pilot.yaml")
    assert set(config["games"]) == {"1120", "dieroll", "pms"}


def test_print_counts_cli_matches_config(monkeypatch, capsys):
    code = runner.main(
        ["--config", str(CONFIGS / "engineering_pilot.yaml"), "--print-counts"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "TOTAL: 720" in out

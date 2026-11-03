# Audit self-consistency tests: the machine-generated coverage audit must
# match the merged registry's numbers exactly and its markdown must be
# regenerated from the same rows (never hand-edited).
#   test_audit_rows_sum_to_grid_totals — experiments and contrasts sum to
#       31/38 with every experiment status filled in.
#   test_audit_counts_resolve_report_inconsistency — the audit's recorded
#       resolution states 28/38 pre-restoration (not 29, not 35).
#   test_markdown_is_regenerated_from_rows — the checked-in markdown equals
#       a fresh render of the audit rows.
#   test_every_grid_experiment_has_one_row — no duplicated or missing
#       experiment rows inside the grid.
from pathlib import Path

AUDIT_DOC = (
    Path(__file__).resolve().parents[3] / "scripts" / "twin2k10r"
    / "stimuli_restored" / "EXPERIMENT_COVERAGE_AUDIT.md"
)


def test_audit_rows_sum_to_grid_totals(restored_pkg):
    rows = restored_pkg.audit_rows()
    grid = [row for row in rows if row["in_grid"]]
    assert len(grid) == 31
    assert sum(row["n_contrasts"] for row in grid) == 38
    assert all(row["status"] for row in grid)


def test_audit_counts_resolve_report_inconsistency(restored_pkg):
    resolution = restored_pkg.audit_resolution()
    assert resolution["pre_restoration_reachable_contrasts"] == 28
    assert resolution["pre_restoration_rejected_figures"] == [29, 35]
    assert resolution["post_restoration_reachable_contrasts"] == 38
    assert resolution["withheld_experiments"] == 6
    assert resolution["withheld_contrasts"] == 10


def test_markdown_is_regenerated_from_rows(restored_pkg):
    rendered = restored_pkg.render_audit_markdown()
    assert rendered == AUDIT_DOC.read_text(encoding="utf-8")


def test_every_grid_experiment_has_one_row(restored_pkg):
    names = [row["name"] for row in restored_pkg.audit_rows() if row["in_grid"]]
    assert len(names) == len(set(names)) == 31

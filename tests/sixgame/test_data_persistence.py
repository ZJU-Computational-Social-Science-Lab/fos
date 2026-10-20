"""Tests that experiment data never lives only inside a worktree.

Each test checks one plain promise:

- test_default_out_dir_is_data_root_run_id_outside_repo: by default the
  runner writes to a permanent folder outside the repository.
- test_records_survive_worktree_deletion: after a worktree folder is
  deleted, the collected records and captured requests are still there.
- test_resume_after_deletion_skips_completed_no_duplicates: restarting
  after the deletion skips finished samples and never writes a copy.
- test_records_never_in_git_status: the repository's git status stays
  clean of data files after a run.
- test_backup_round_trip_checksums: a backup copies every file, and
  verifying the backup against its checksum list passes.
- test_preserved_datasets_match_source_hashes: the old result folders
  copied into the data root are byte-identical to the originals.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
for _p in (str(_SCRIPTS), str(_SCRIPTS / "sixgame")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import data_root as data_root_module  # noqa: E402
import runner  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def data_env(tmp_path, monkeypatch):
    """Point the data root at a temp folder for the whole test."""
    root = tmp_path / "experiment-data" / "fos" / "sixgame"
    monkeypatch.setenv("SIXGAME_DATA_ROOT", str(root))
    return root


def _run_one_cell_plan(out_dir: Path, personas_dir: Path) -> dict:
    """Run a tiny offline (dry-transport) plan into out_dir."""
    config = runner.default_config("engineering")
    config["personas"] = 1
    config["draws_per_cell"] = 1
    config["games"] = {"1120": {"variants": ["basic"]}}
    config["models"] = ["deepseek-v4-flash"]
    config["arms"] = ["no_persona"]
    names = ["synthetic_test_persona"]
    plan = runner.build_plan(config, names, 1) + runner.probe_plan(config, names, 1)
    route_map = {m: "dry" for m in config["models"]}
    summary = runner.run_plan(plan, out_dir, out_dir, {}, route_map, 1)
    import sixgame.transport as tmod

    captured = out_dir / "captured_requests.jsonl"
    with captured.open("w", encoding="utf-8") as fh:
        for payload in tmod.DRY_CAPTURED:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return summary


def test_default_out_dir_is_data_root_run_id_outside_repo(data_env):
    """Default output goes to the permanent data root, outside the repo."""
    out_dir = data_root_module.resolve_out_dir(None, "engineering_pilot_corrective")
    assert out_dir == data_env / "engineering_pilot_corrective"
    assert out_dir.is_absolute()
    assert REPO_ROOT not in out_dir.parents


def test_records_survive_worktree_deletion(data_env, tmp_path, monkeypatch):
    """Records written to the data root survive deleting the worktree."""
    fake_worktree = tmp_path / "worktree"
    fake_worktree.mkdir()
    monkeypatch.chdir(fake_worktree)
    out_dir = data_root_module.resolve_out_dir(None, "engineering_pilot_corrective")
    summary = _run_one_cell_plan(out_dir, REPO_ROOT)
    assert summary["completed"] > 0
    import shutil

    shutil.rmtree(fake_worktree)
    jsonl_files = list(out_dir.glob("*.jsonl"))
    assert jsonl_files, "records must persist outside the worktree"
    for path in jsonl_files:
        assert path.stat().st_size > 0
    assert (out_dir / "captured_requests.jsonl").exists()


def test_resume_after_deletion_skips_completed_no_duplicates(
    data_env, tmp_path, monkeypatch
):
    """A restarted run skips finished samples and writes no duplicates."""
    monkeypatch.chdir(tmp_path)
    out_dir = data_root_module.resolve_out_dir(None, "engineering_pilot_corrective")
    first = _run_one_cell_plan(out_dir, REPO_ROOT)
    counts_before = {
        p.name: len(p.read_text().splitlines()) for p in out_dir.glob("*.jsonl")
    }
    # Simulate a fresh restart (e.g. after the worktree was recreated).
    second = _run_one_cell_plan(out_dir, REPO_ROOT)
    assert second["skipped"] == first["completed"] + first["skipped"]
    counts_after = {
        p.name: len(p.read_text().splitlines()) for p in out_dir.glob("*.jsonl")
    }
    assert counts_after == counts_before, "resume must not append duplicates"


def test_records_never_in_git_status(data_env, tmp_path, monkeypatch):
    """After a run, the repo's git status shows no data files."""
    monkeypatch.chdir(REPO_ROOT)
    out_dir = data_root_module.resolve_out_dir(None, "engineering_pilot_corrective")
    _run_one_cell_plan(out_dir, REPO_ROOT)
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True
    )
    lines = result.stdout.decode("utf-8").splitlines()
    data_lines = [ln for ln in lines if ln.endswith(".jsonl")]
    assert not data_lines, f"data leaked into git status: {data_lines}"


def test_backup_round_trip_checksums(data_env):
    """A backup copies everything, and --verify confirms the checksums."""
    import backup_data

    out_dir = data_root_module.resolve_out_dir(None, "engineering_pilot_corrective")
    _run_one_cell_plan(out_dir, REPO_ROOT)
    backup_dir = data_env.parent / "sixgame-backups" / "testrun"
    backup_data.backup(data_env, backup_dir)
    problems = backup_data.verify(backup_dir)
    assert problems == []
    src_hashes = {
        p.relative_to(data_env).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(data_env.rglob("*"))
        if p.is_file()
    }
    dst_hashes = {
        p.relative_to(backup_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(backup_dir.rglob("*"))
        if p.is_file() and p.name != backup_data.MANIFEST_NAME
    }
    assert src_hashes == dst_hashes


def test_preserved_datasets_match_source_hashes(data_env, tmp_path):
    """Copied old datasets are byte-identical to the originals."""
    source = tmp_path / "repo-results" / "sixgame"
    for run_id in data_root_module.PRESERVED_RUN_IDS:
        run_dir = source / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "decisions.jsonl").write_text('{"choice": 11}\n')
        (run_dir / "notes.txt").write_text("provenance copy\n")
    counts = data_root_module.preserve_datasets(source, data_env)
    assert set(counts) == set(data_root_module.PRESERVED_RUN_IDS)
    problems = data_root_module.verify_manifest(
        data_env, data_env / data_root_module.PRESERVATION_MANIFEST
    )
    assert problems == []
    for run_id in data_root_module.PRESERVED_RUN_IDS:
        src = source / run_id / "decisions.jsonl"
        dst = data_env / run_id / "decisions.jsonl"
        assert src.read_bytes() == dst.read_bytes()


def test_manifest_ignores_the_manifest_itself(tmp_path):
    """Writing the fingerprint file twice in a row still verifies."""
    folder = tmp_path / "data"
    folder.mkdir()
    (folder / "a.jsonl").write_text("{}\n")
    manifest = folder / data_root_module.PRESERVATION_MANIFEST
    data_root_module.write_manifest(folder, manifest)
    data_root_module.write_manifest(folder, manifest)
    assert data_root_module.verify_manifest(folder, manifest) == []

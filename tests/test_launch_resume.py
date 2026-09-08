# Locked tests for the launch wrapper's checkpoint/resume guarantees.
#
# WHY THESE TESTS EXIST: the R1 overnight run (132k calls, ~9-10 h) must be
# stoppable at any moment (Ctrl-C, SIGKILL, power loss) and resumable with
# the exact same command plus --resume, without losing completed records or
# duplicating them. These tests pin the wrapper's resume contract as it is
# implemented: persona-pool draws flush per accepted persona (an interrupted
# pool phase keeps its progress), and sweep legs are leg-granular -- a leg's
# records are written only when the whole leg completes, so the unit of
# resume is the (depth x blinding) leg, not the single call.
#
# THE CONTRACT THESE TESTS PIN (TASK-1522):
#   1. A leg counts as done only when its own files AND its manifest exist;
#      a partial records file without a manifest is NOT done (it is re-run
#      and rewritten on resume, never appended to, so no duplicates can
#      accumulate).
#   2. --resume plans exactly the legs missing from disk -- every leg that
#      is already done is skipped as a whole unit.
#   3. The guard refuses a NON-resume start into a directory holding any
#      durable sign of a run (manifest.json, pools.json, or leg files): a
#      fresh start there would overwrite completed stochastic records.
#   4. The run-level manifest.json is written as a "running" marker as soon
#      as a run starts, so an interrupted run is recognisable and its true
#      start time survives every resume.
#   5. The FINAL run manifest lists every planned leg exactly once, in plan
#      order: legs finished in earlier invocations (rebuilt from their own
#      files) and legs finished in the latest invocation both appear -- no
#      duplicates, no gaps; the earliest start is kept, every resume is
#      recorded under "resumed", and the pools summary is carried forward
#      when the pool phase was skipped. Resuming a fully completed run
#      therefore never wipes the manifest.
#   6. The persona-pool phase never re-draws the whole batch when a partial
#      pool already exists on disk: it tops up only the products still
#      short of K accepted personas (and is skipped entirely when a
#      matching pools.json exists). No GPU calls are spent on finished
#      products.
#
# Every test runs offline (no model server, no manager, no GPU): resume
# decisions are made purely from files on disk.
import json
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from launch_support import Settings  # noqa: E402

# Five planned legs: the four R1 (depth x blinding) legs plus one more, so
# the task's "3 of 5 planned units done -> exactly the 2 missing units are
# planned" phrasing is exercised literally.
FIVE_TARGETS = [
    {"depth": depth, "blinding": blinding}
    for depth, blinding in [
        ("none", "blinded"),
        ("none", "unblinded"),
        ("demographics", "blinded"),
        ("demographics", "unblinded"),
        ("stage2", "blinded"),
    ]
]
FIVE_KEYS = [(t["depth"], t["blinding"]) for t in FIVE_TARGETS]
SAFE_MODEL = "vendor_model"


def _settings(tmp_path: Path) -> Settings:
    """One launch configuration pointed at a throwaway directory."""
    return Settings(
        model="vendor/model",
        port=8080,
        manager_url="http://127.0.0.1:9",  # nothing listens here; never called
        base_url="http://127.0.0.1:9",
        out=tmp_path,
        run_name="resume-probe",
        pool_seed=42,
        pool_overdraw=1.2,
        seed=7,
        draws=1,
        progress_every=10,
        products_path="data/configs/unblinding_products.json",
    )


def _plan(targets: list[dict[str, str]]) -> dict:
    """A plan object shaped like launch_grid._plan's output."""
    return {
        "profile": "R1",
        "k": 100,
        "levels": [0.0, 100.0],
        "legs": [{**target, "calls": 4} for target in targets],
        "sweep_calls": len(targets) * 4,
        "pool_draws": 20,
        "depths": ["none", "demographics"],
    }


def _write_leg(run_dir: Path, depth: str, blinding: str, records: int = 3) -> None:
    """Write one finished leg's files exactly as the wrapper leaves them."""
    leg_dir = run_dir / f"{depth}_{blinding}"
    leg_dir.mkdir(parents=True, exist_ok=True)
    with (leg_dir / f"{SAFE_MODEL}_{blinding}.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for index in range(records):
            handle.write(
                json.dumps(
                    {"succeeded": True, "elapsed_seconds": 0.5, "draw": index}
                )
                + "\n"
            )
    (leg_dir / f"{SAFE_MODEL}_{blinding}.csv").write_text("", encoding="utf-8")
    (leg_dir / "manifest.json").write_text(
        json.dumps({"depth": depth, "blinding": blinding}), encoding="utf-8"
    )


def _leg_result(depth: str, blinding: str) -> dict:
    """A leg result exactly as launch_sweep._save_leg_outputs records it."""
    return {
        "depth": depth,
        "blinding": blinding,
        "ok": True,
        "records": 3,
        "parsed": 3,
        "parse_rate": 1.0,
        "mean_elapsed": 0.5,
        "files": ["x.jsonl", "x.csv", "manifest.json"],
    }


def _manifest_payload(
    settings: Settings,
    plan: dict,
    products_path: Path,
    started: str,
    finished: str,
    *,
    legs: list[dict],
    pools: dict | None,
    state: str,
) -> dict:
    """The on-disk run-manifest shape the wrapper writes (hand-built here so
    the tests never depend on the writer under test for their fixtures)."""
    return {
        "run_name": settings.run_name,
        "profile": plan["profile"],
        "model": settings.model,
        "port": settings.port,
        "base_url": settings.base_url,
        "manager_url": settings.manager_url,
        "commit_sha": "deadbeef",
        "products_file": str(products_path),
        "levels": plan["levels"],
        "draws": settings.draws,
        "seed": settings.seed,
        "k": plan["k"],
        "pool_seed": settings.pool_seed,
        "pool_overdraw": settings.pool_overdraw,
        "planned_sweep_calls": plan["sweep_calls"],
        "planned_pool_draws": plan["pool_draws"],
        "started": started,
        "finished": finished,
        "ok": all(leg.get("ok") for leg in legs) if state == "complete" else None,
        "state": state,
        "legs": legs,
        "pools": pools,
        "resumed": None,
        "argv": ["launch_grid.py"],
    }


def _run_manifest(run_dir: Path) -> dict:
    """Read the run-level manifest on disk."""
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def _assert_legs_exactly_once(payload: dict) -> None:
    """The merged manifest lists each planned leg exactly once, in order."""
    merged = [(leg["depth"], leg["blinding"]) for leg in payload["legs"]]
    assert merged == FIVE_KEYS, f"legs {merged} != planned {FIVE_KEYS}"
    assert len(merged) == len(set(merged)), f"duplicate legs in {merged}"


# --- 1. What counts as done, and what a resume plans ------------------------


def test_leg_with_partial_records_but_no_manifest_is_not_done():
    """A leg with records but no manifest is NOT done: on resume it is re-run
    from scratch and its file rewritten (never appended), so a partial leg
    never leaves a half-finished or duplicated record set."""
    from launch_sweep import _leg_is_done

    with tempfile.TemporaryDirectory() as tmp:
        leg_dir = Path(tmp) / "none_blinded"
        leg_dir.mkdir()
        (leg_dir / f"{SAFE_MODEL}_blinded.jsonl").write_text(
            json.dumps({"succeeded": True}) + "\n", encoding="utf-8"
        )
        assert not _leg_is_done(
            Path(tmp), SAFE_MODEL, {"depth": "none", "blinding": "blinded"}
        )


def test_resume_plans_only_the_legs_missing_from_disk():
    """A run with 3 of 5 legs already finished on disk resumes by planning
    exactly the 2 missing legs -- never the finished ones."""
    from launch_grid import _pending_legs

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        for depth, blinding in FIVE_KEYS[:3]:
            _write_leg(run_dir, depth, blinding, records=3)
        pending = _pending_legs(
            Namespace(resume=True), run_dir, SAFE_MODEL, FIVE_TARGETS
        )
        pending_keys = {(leg["depth"], leg["blinding"]) for leg in pending}
        assert pending_keys == set(FIVE_KEYS[3:])


# --- 2. The run-directory guard ---------------------------------------------


def _call_run_guard(tmp_path: Path) -> int:
    """Drive launch_grid._run far enough to hit the guard: any durable state
    must make a non-resume start return exit code 2 before any network or
    model call happens."""
    from launch_grid import _run

    settings = _settings(tmp_path)
    products = [{"category": "c", "product": "p", "regular_price": 10.0}]
    return _run(
        Namespace(resume=False),
        _plan(FIVE_TARGETS),
        products,
        Path("products.json"),
        settings,
    )


def test_non_resume_start_into_dir_with_manifest_is_refused():
    """A directory that already has a run manifest refuses a non-resume start."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = _settings(tmp_path).out / "resume-probe"
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
        assert _call_run_guard(tmp_path) == 2


def test_non_resume_start_into_dir_with_pools_json_is_refused():
    """A directory holding only pools.json (an interrupted pool phase) must
    refuse a non-resume start: a fresh run would otherwise overwrite the
    pools work silently."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = _settings(tmp_path).out / "resume-probe"
        run_dir.mkdir(parents=True)
        (run_dir / "pools.json").write_text("{}", encoding="utf-8")
        assert _call_run_guard(tmp_path) == 2


def test_non_resume_start_into_dir_with_leg_files_is_refused():
    """A directory holding finished leg files (even with no run-level
    manifest) refuses a non-resume start: re-running would overwrite
    completed stochastic records with fresh draws."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = _settings(tmp_path).out / "resume-probe"
        _write_leg(run_dir, "none", "blinded", records=3)
        assert _call_run_guard(tmp_path) == 2


# --- 3. The run manifest: running marker, resume merge, no wipe ------------


def test_running_marker_manifest_is_written_with_ok_none():
    """The manifest writer records a 'running' marker (no legs, ok null) so
    an interrupted run is recognisable and its true start time survives."""
    from launch_manifest import _write_run_manifest

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        settings = _settings(tmp_path)
        run_dir = settings.out / settings.run_name
        run_dir.mkdir()
        _write_run_manifest(
            settings,
            _plan(FIVE_TARGETS),
            Path("products.json"),
            run_dir,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            [],
            None,
            targets=FIVE_TARGETS,
            safe_model=SAFE_MODEL,
            prior=None,
            resume_invocation=False,
            state="running",
        )
        payload = _run_manifest(run_dir)
        assert payload["state"] == "running"
        assert payload["ok"] is None
        assert payload["legs"] == []
        assert payload["started"] == "2026-01-01T00:00:00+00:00"


def test_resume_of_completed_run_keeps_the_full_manifest():
    """Re-running --resume against an already-completed run is a safe no-op:
    the final manifest keeps every leg and the pools summary instead of
    being wiped to an empty stub (the pre-fix behaviour wiped it)."""
    from launch_grid import _run

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        settings = _settings(tmp_path)
        run_dir = settings.out / settings.run_name
        run_dir.mkdir(parents=True)
        products_path = Path("products.json")
        for depth, blinding in FIVE_KEYS:
            _write_leg(run_dir, depth, blinding, records=3)
        pools_summary = {"k": 100, "products": 40}
        (run_dir / "manifest.json").write_text(
            json.dumps(
                _manifest_payload(
                    settings,
                    _plan(FIVE_TARGETS),
                    products_path,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T06:00:00+00:00",
                    legs=[_leg_result(d, b) for d, b in FIVE_KEYS],
                    pools=pools_summary,
                    state="complete",
                )
            ),
            encoding="utf-8",
        )
        assert _run(Namespace(resume=True), _plan(FIVE_TARGETS), [],
                    products_path, settings) == 0
        payload = _run_manifest(run_dir)
        _assert_legs_exactly_once(payload)
        assert payload["state"] == "complete" and payload["ok"] is True
        assert payload["pools"] == pools_summary  # carried, not wiped
        assert payload["started"] == "2026-01-01T00:00:00+00:00"  # earliest kept
        assert len(payload["resumed"]) == 1  # the no-op resume is recorded
        assert payload["resumed"][0]["legs"] == []


def test_resume_after_interrupted_run_merges_every_leg_exactly_once():
    """A run killed mid-way (running marker, 3 legs finished) that is then
    resumed and completes the other 2 merges into a final manifest listing
    all 5 legs exactly once: the 3 finished legs come from their own files,
    the 2 new ones from the resumed invocation -- no duplicates, no gaps."""
    from launch_manifest import _load_run_manifest, _write_run_manifest

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        settings = _settings(tmp_path)
        run_dir = settings.out / settings.run_name
        run_dir.mkdir(parents=True)
        products_path = Path("products.json")
        # Invocation 1 wrote its running marker, finished 3 legs, then died.
        (run_dir / "manifest.json").write_text(
            json.dumps(
                _manifest_payload(
                    settings,
                    _plan(FIVE_TARGETS),
                    products_path,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:01:00+00:00",
                    legs=[],
                    pools=None,
                    state="running",
                )
            ),
            encoding="utf-8",
        )
        for depth, blinding in FIVE_KEYS[:3]:
            _write_leg(run_dir, depth, blinding, records=3)
        # Invocation 2 (resume) completes the 2 remaining legs.
        _write_run_manifest(
            settings,
            _plan(FIVE_TARGETS),
            products_path,
            run_dir,
            "2026-01-02T00:00:00+00:00",
            "2026-01-02T02:00:00+00:00",
            [_leg_result("demographics", "unblinded"),
             _leg_result("stage2", "blinded")],
            {"k": 100, "products": 40},
            targets=FIVE_TARGETS,
            safe_model=SAFE_MODEL,
            prior=_load_run_manifest(run_dir),
            resume_invocation=True,
            state="complete",
        )
        payload = _run_manifest(run_dir)
        _assert_legs_exactly_once(payload)
        assert all(leg["ok"] for leg in payload["legs"])
        assert payload["started"] == "2026-01-01T00:00:00+00:00"  # earliest kept
        assert len(payload["resumed"]) == 1
        assert set(payload["resumed"][0]["legs"]) == {
            "demographics_unblinded",
            "stage2_blinded",
        }


def test_done_leg_summary_read_back_from_its_own_files():
    """A finished leg's manifest entry (record counts, parse rate, mean
    elapsed) is rebuilt from its own jsonl when the run-level manifest never
    recorded it -- that is how an interrupted run's completed legs re-enter
    the final merged manifest."""
    from launch_manifest import _leg_done_result

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        leg_dir = run_dir / "none_blinded"
        leg_dir.mkdir()
        with (leg_dir / f"{SAFE_MODEL}_blinded.jsonl").open(
            "w", encoding="utf-8"
        ) as handle:
            for succeeded, elapsed in [(True, 0.4), (False, 0.8), (True, 0.6)]:
                handle.write(
                    json.dumps(
                        {"succeeded": succeeded, "elapsed_seconds": elapsed}
                    )
                    + "\n"
                )
        (leg_dir / f"{SAFE_MODEL}_blinded.csv").write_text("", encoding="utf-8")
        (leg_dir / "manifest.json").write_text("{}", encoding="utf-8")
        summary = _leg_done_result(
            run_dir, SAFE_MODEL, {"depth": "none", "blinding": "blinded"}
        )
        assert summary is not None and summary["ok"] is True
        assert summary["records"] == 3
        assert summary["parsed"] == 2
        assert summary["parse_rate"] == 2 / 3
        assert abs(summary["mean_elapsed"] - 0.6) < 1e-9


# --- 4. The persona-pool phase: top up, never regenerate --------------------


def _fake_generate_personas(commands: list, short_product: str):
    """A stand-in for the generate_personas subprocess that records every
    command and, for the single-product top-up of `short_product`, appends
    three accepted personas to that product's folder (as the real tool does
    per drawn persona)."""

    def fake_run(cmd: list, **_kwargs) -> None:
        commands.append(cmd)
        if "--product" in cmd:
            folder = Path(cmd[cmd.index("--out") + 1])
            with (folder / "personas.jsonl").open("a", encoding="utf-8") as handle:
                for _ in range(3):
                    handle.write(
                        json.dumps({"age": 32, "gender": "female"}) + "\n"
                    )

    return fake_run


def _pool_products_dir(tmp_path: Path) -> tuple[Settings, Path, Path]:
    """Products Cola (5 personas on disk) and Chips (1), plus the products
    file; returns (settings, run_dir, products_path)."""
    settings = _settings(tmp_path)
    run_dir = settings.out / settings.run_name
    products_work = run_dir / "pools_work"
    cola_dir = products_work / "Cola_12_oz"
    cola_dir.mkdir(parents=True)
    with (cola_dir / "personas.jsonl").open("w", encoding="utf-8") as handle:
        for _ in range(5):
            handle.write(json.dumps({"age": 30}) + "\n")
    chips_dir = products_work / "Potato_Chips"
    chips_dir.mkdir(parents=True)
    with (chips_dir / "personas.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"age": 30}) + "\n")
    products_path = tmp_path / "products.json"
    products_path.write_text(
        json.dumps(
            {
                "products": [
                    {"category": "Soft Drinks", "product": "Cola 12 oz",
                     "regular_price": 1.99},
                    {"category": "Chips", "product": "Potato Chips",
                     "regular_price": 2.99},
                ]
            }
        ),
        encoding="utf-8",
    )
    return settings, run_dir, products_path


def _products() -> list[dict]:
    """The two products _pool_products_dir wrote persona folders for."""
    return [
        {"category": "Soft Drinks", "product": "Cola 12 oz",
         "regular_price": 1.99},
        {"category": "Chips", "product": "Potato Chips",
         "regular_price": 2.99},
    ]


def test_pool_phase_resume_only_tops_up_products_still_short():
    """When a partial pool already exists on disk (an interrupted pool
    phase), the resume path never re-draws the whole batch: it tops up only
    the products still short of K, then subsamples exactly K per product."""
    import launch_support as support_module
    from launch_support import _pool_phase

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        settings, run_dir, products_path = _pool_products_dir(tmp_path)
        commands: list = []
        original_run = support_module.subprocess.run
        support_module.subprocess.run = _fake_generate_personas(
            commands, "Potato Chips"
        )
        try:
            summary = _pool_phase(
                settings, _products(), products_path, run_dir, 3,
                lambda _text: None,
            )
        finally:
            support_module.subprocess.run = original_run

        # The full batch (--products-file) must never run again; only the
        # single-product top-up for the short product Chips is allowed.
        assert [c for c in commands if "--products-file" in c] == [], (
            "partial pool triggered a full redraw"
        )
        topups = [c for c in commands if "--product" in c]
        assert len(topups) == 1 and topups[0][topups[0].index("--product") + 1] == (
            "Potato Chips"
        )
        assert summary["products"] == 2
        assert (run_dir / "pools.json").exists()
        for flat in (run_dir / "pools" / "cola_12_oz.jsonl",
                     run_dir / "pools" / "potato_chips.jsonl"):
            lines = [ln for ln in flat.read_text(encoding="utf-8").splitlines() if ln]
            assert len(lines) == 3, f"{flat} holds {len(lines)} personas, not 3"


def test_pool_phase_skipped_entirely_when_pools_json_matches():
    """A completed pool phase (matching pools.json) is skipped on resume with
    zero further persona draws."""
    import launch_support as support_module
    from launch_support import _pool_phase

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        settings = _settings(tmp_path)
        run_dir = settings.out / settings.run_name
        run_dir.mkdir(parents=True)
        products_path = tmp_path / "products.json"
        products_path.write_text(
            json.dumps(
                {"products": [{"category": "c", "product": "Cola 12 oz",
                               "regular_price": 1.99}]}
            ),
            encoding="utf-8",
        )
        existing = {
            "k": 3,
            "pool_seed": 42,
            "model": "vendor/model",
            "products": 1,
            "requested": 4,
            "accepted_total": 3,
            "accepted_min": 3,
        }
        (run_dir / "pools.json").write_text(
            json.dumps(existing), encoding="utf-8"
        )
        commands: list = []
        original_run = support_module.subprocess.run
        support_module.subprocess.run = _fake_generate_personas(commands, "")
        try:
            summary = _pool_phase(
                settings,
                [{"category": "c", "product": "Cola 12 oz",
                  "regular_price": 1.99}],
                products_path,
                run_dir,
                3,
                lambda _text: None,
            )
        finally:
            support_module.subprocess.run = original_run

        assert commands == []
        assert summary == existing

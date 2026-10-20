# sixgame scripts — experiment runner, analysis, and data safety

This folder holds the code for the three-game persona experiment: planning
samples, calling language models, saving every answer, resuming interrupted
runs, checking the plan before spending money, and analyzing the results.

## Where the data lives (DATA_ROOT)

All experiment data is written to one permanent folder **outside every git
worktree**:

    ~/experiment-data/fos/sixgame/

Set the environment variable `SIXGAME_DATA_ROOT` to point somewhere else
(tests do this). Each run writes to its own subfolder named after the run
ID, for example `engineering_pilot` or `engineering_pilot_corrective`:

    runner.py --run-id engineering_pilot_corrective ...

The default run ID is `engineering_pilot_corrective`. `--out-dir` still
works but must point **inside** the data root; `--allow-any-outdir`
overrides that for tests only.

**No data in git, ever.** Because the data root is outside the repository,
raw observations never show up in `git status`, and no result folder is
ever committed or force-added. The old result folders were copied into the
data root once (hash-checked, see `PRESERVATION_MANIFEST.sha256`); the
originals in the repo are untouched for provenance.

## Backup and verify

    python scripts/sixgame/backup_data.py                 # timestamped backup
    python scripts/sixgame/backup_data.py --verify DIR    # check a backup
    python scripts/sixgame/backup_data.py --preserve      # (re)copy old repo datasets

Backups go to `~/experiment-data/fos/sixgame-backups/<timestamp>/` with a
`MANIFEST.sha256` checksum list; `--verify` re-checks every file.

## Data-loss log

Any lost observation is recorded in
`~/experiment-data/fos/sixgame/DATA_LOSS_LOG.md`. Lost observations are
never counted toward frozen sample quotas.

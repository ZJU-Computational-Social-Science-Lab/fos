# VALIDATION REPORT

- **pool size: PASS** — 100 lines, ids 0-99
- **persona-to-respondent truth: PASS** — every value equals the panel record of the same pid
- **marginals vs panel: PASS** — sex x age max gap 0.41 pp; single-variable gaps within the ±1 rounding unit; reference is the panel, not the census
- **one shared pool across conditions: PASS** — single pool file; its sha256 is asserted per model block
- **no leaking fields / placeholders: PASS** — all keys within the 'B' whitelist; zero placeholders; zero banned outcome tokens
- **seed reproducibility: PASS** — fresh replay of seed 42 reproduces the pid list exactly (100 pids)
- **full panel: PASS** — 2,058 respondents loaded

**Overall: PASS — inference may start**

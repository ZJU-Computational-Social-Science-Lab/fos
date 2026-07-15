# FOS Bug Log

| ID | Date | Sev | Demo-path? | Module | Summary | Status | Regression test | Fixed in |
|----|------|-----|------------|--------|---------|--------|-----------------|----------|
| — | — | — | — | — | _(no bugs filed yet)_ | — | — | — |

## Severity

- **P0** — blocks a flow, no workaround. Fix before freeze.
- **P1** — works, degraded or confusing.
- **P2** — cosmetic / rare edge.

## Rules
1. **Demo-path column beats severity.** A P1 on slide 3 outranks a P0 in a feature you'll never show.
2. **Every P0 fix ships with a committed regression test.** Non-negotiable — Ziwei's #3 refactor lands while you're presenting, and an uncommitted manual check will not survive it.

## Bug entry template

### BUG-XXX: [Title]
**Date:** 2026-07-XX   **Severity:** P0/P1/P2   **Demo-path:** Y/N
**Found by:** Justin / Ziwei / audience
**Module:** [e.g. AI Scientist → json_repair]
**Steps to reproduce:** [numbered, from a clean demo_seed.db]
**Expected / Actual:**
**Environment:** browser, commit SHA, provider + base URL + model, locale, OS
**Evidence:** [screenshot / HAR / console log / server log]
**Status:** OPEN / IN PROGRESS / FIXED / WONTFIX
**Fixed by:** [commit]   **Regression test:** [path — REQUIRED for P0]
**Verified:** YYYY-MM-DD by [name]

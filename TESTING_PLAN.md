# FOS Platform — Deep Testing & Bug-Fixing Plan

**Task:** #6 from the development plan (systematic test matrix)
**Period:** 2026-07-08 – 2026-07-21 (10 working days)
**Tester:** Justin Miller
**Support:** Zheng Ziwei (reproduction, recording, verification)
**Repo:** `/home/justin/Documents/ZJU work/fos`

---

## Phase 0: Setup & Environment (Day 1 — 2026-07-08)

### 0.1 Testing Environment Setup

Ensure the testing environment matches the development environment from Task #1:

| Requirement | Expected | Verification |
|-------------|----------|-------------|
| Python | 3.12 | `python3 --version` |
| Node.js | 22.x | `node --version` |
| npm | 10.x | `npm --version` |
| Backend venv | `venv/` activated | `source venv/bin/activate` |
| Frontend deps | `npm ci` done | `ls frontend/node_modules/.package-lock.json` |
| Database | `fos.db` writable | `touch fos.db` |
| Browser | Latest Chromium | Playwright install check |
| LLM provider | At least one configured | Check Settings → Providers page |
| Test DB | Separate `test_fos.db` | Configure via env var |

**Action items:**
- [ ] Create `test_fos.db` isolation (set `FOS_DATABASE_URL` to a separate file for testing)
- [ ] Verify backend starts: `cd src && uvicorn fos.backend.main:app --port 8000`
- [ ] Verify frontend starts: `cd frontend && npm run dev`
- [ ] Run existing test suites to capture baseline

### 0.2 Inventory Existing Tests

Run these and save the output for baseline comparison:

```bash
# Backend unit + integration tests
cd ~/Documents/ZJU\ work/fos
source venv/bin/activate
python -m pytest tests/ -v --tb=short --durations=10 2>&1 | tee test_results/baseline-backend-$(date +%F).log

# Frontend unit tests
cd frontend
npm run test:run 2>&1 | tee ../test_results/baseline-frontend-$(date +%F).log

# E2E smoke tests
npm run test:e2e:smoke 2>&1 | tee ../test_results/baseline-e2e-smoke-$(date +%F).log

# E2E health check
npm run test:e2e:health 2>&1 | tee ../test_results/baseline-e2e-health-$(date +%F).log
```

**Inventory document:** Create `test_results/TEST_INVENTORY.md` with:
- Counts of passing/failing/skipped tests per category
- Known flaky tests
- Tests that require a live LLM provider

### 0.3 Bug Tracking Setup

Create `test_results/BUG_LOG.md` with this template:

```markdown
# Bug Log

| ID | Date | Severity | Module | Summary | Status | Fixed In |
|----|------|----------|--------|---------|--------|----------|
```

**Severity levels:**
- **P0** — Blocks user flow, no workaround (must fix before Beta)
- **P1** — User flow works but with degraded experience or confusing behaviour
- **P2** — Minor issue, cosmetic, edge case

### 0.4 Test Data & Scenarios

Ensure the following test data is available:

- [ ] Default scene configurations loaded
- [ ] At least one LLM provider configured (LM Studio local is preferred)
- [ ] 2+ test user accounts (can register fresh)
- [ ] Sample research documents for AI Scientist testing
- [ ] Network topology presets loaded

---

## Phase 1: Core Flows — Happy Path (Days 2-4 — 2026-07-09 to 2026-07-11)

### 1.1 Authentication & Login

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| AUTH-01 | Register new user | App running, no existing session | 1. Navigate to `/register`<br>2. Fill email, username, password<br>3. Submit | User created, redirected to `/login`, success toast shown | Duplicate email, weak password, empty fields | P0 |
| AUTH-02 | Login with valid credentials | Registered user exists | 1. Navigate to `/login`<br>2. Enter email + password<br>3. Submit | Redirected to `/dashboard`, JWT set, user name in navbar | — | P0 |
| AUTH-03 | Login with wrong password | Registered user exists | 1. Enter email + wrong password<br>2. Submit | Error message shown, not redirected | — | P1 |
| AUTH-04 | Token refresh | User logged in, wait >15 min | 1. Leave tab idle >15 min<br>2. Refresh page | Session preserved, no re-login required | Token expired while form filling | P0 |
| AUTH-05 | Logout | User logged in | 1. Click logout button<br>2. Confirm | Redirected to `/login`, no API calls succeed after | Browser back after logout | P1 |
| AUTH-06 | Protected routes | No active session | 1. Navigate to `/simulations/saved` | Redirected to `/login` with return URL | Deep-linking to simulation pages | P0 |

### 1.2 Experiment Creation — Full Flow

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| CRE-01 | Create experiment via AI Scientist | User logged in, LLM provider configured | 1. Click "New Experiment"<br>2. Select AI Scientist mode<br>3. Describe research question<br>4. Click "Generate Draft"<br>5. Review draft<br>6. Confirm | Draft generated with scene, agents, params; experiment created; redirected to workspace | Empty description, very long description | P0 |
| CRE-02 | Create experiment from template | Templates exist in DB | 1. Click "New Experiment"<br>2. Select "From Template"<br>3. Pick a template<br>4. Review parameters<br>5. Create | Experiment created with template values; redirected to workspace | Template with missing scene, deleted template | P0 |
| CRE-03 | Custom experiment — step-by-step wizard | User logged in | 1. Click "New Experiment"<br>2. Select "Custom"<br>3. Step 1: Choose interaction type<br>4. Step 2: Choose starter template<br>5. Step 3: Configure scenario parameters<br>6. Step 4: Configure agents (names, roles, LLM models)<br>7. Step 5: Configure network topology<br>8. Step 6: Configure structure/rounds<br>9. Review and create | All 6 steps navigable; values persist across steps; experiment created on final step | Browser back during wizard, refresh mid-wizard | P0 |
| CRE-04 | Parameter consistency: frontend → backend | — | 1. Create experiment with specific parameters<br>2. Note all values set in frontend<br>3. Fetch experiment details via API<br>4. Compare every parameter | All frontend-set parameters match what backend stores | Scene-specific defaults, empty parameter values | P1 |
| CRE-05 | AI Scientist draft regeneration | First draft generated | 1. Click "Regenerate" on draft | New draft appears; old draft discarded | Rapid double-click | P1 |

### 1.3 Simulation Runtime

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| SIM-01 | Start experiment | Experiment created | 1. Navigate to experiment workspace<br>2. Click "Start/Play" | First node (trunk branch) created; status changes from "pending" to "running" | — | P0 |
| SIM-02 | Run trunk branch to completion | Experiment started | 1. Wait for trunk branch to auto-advance or click "Advance" | Agents respond each round; new tree nodes created for each round; status progresses to "completed" | 0 rounds configured, single agent | P0 |
| SIM-03 | Node advancement | Trunk branch at a node | 1. Click "Advance" (or auto-advance fires) | Next round node created; agent actions visible in console | Rapid successive advances | P0 |
| SIM-04 | Auto-advance toggling | Experiment running | 1. Toggle auto-advance ON<br>2. Wait<br>3. Toggle auto-advance OFF | When ON: advances happen automatically at intervals. When OFF: stops advancing | Toggle during mid-advance | P0 |
| SIM-05 | Multiple experiments running | 2+ experiments created | 1. Start experiment A<br>2. Start experiment B<br>3. Switch between tabs | Both progress independently; no cross-contamination of state | Both using same LLM provider | P1 |
| SIM-06 | Simulation pause and resume | Experiment running | 1. Click "Pause"<br>2. Click "Resume" | Pause: no new rounds started. Resume: normal flow continues | Pause during auto-advance | P1 |

### 1.4 Agent Interaction

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| AGT-01 | Agent decision-making visible | Experiment running | 1. Open a completed node<br>2. Click on an agent card | Agent's decision, reasoning, and action shown; profile and history visible | Agent with no history | P0 |
| AGT-02 | Agent communicates with neighbours | Network with >1 agent, experiment running | 1. Observe agent observations in console<br>2. Check agent memory | Agents reference each other's statements or actions; observations reflected in subsequent rounds | Isolated (degree-0) agents | P0 |
| AGT-03 | Agent LLM config applies | Agent configured with specific model | 1. Create experiment<br>2. Set different models per agent<br>3. Run experiment | Each agent uses its specified model; API calls to correct provider | Model not available, provider down | P1 |

### 1.5 Environment Events

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| ENV-01 | Create environment event | Experiment created | 1. Open Host/Intervention panel<br>2. Click "New Event"<br>3. Fill event details (type, description, target agents)<br>4. Save | Event created and listed; appears as pending | Empty description, very long text | P0 |
| ENV-02 | Inject event into simulation | Experiment running | 1. Create an event<br>2. Click "Inject" or schedule it<br>3. Advance simulation | Event appears in agent context at the appropriate round; agents reference it in their decisions | Event injected at exact moment of advance | P0 |
| ENV-03 | Scheduled events | Experiment running | 1. Create event with round schedule<br>2. Run simulation past scheduled round | Event fires automatically at the specified round | Overlapping scheduled events | P1 |
| ENV-04 | Event impact on simulation | Event injected | 1. Compare agent behaviour before and after event injection | Observable change in agent decisions aligned with event content | Event contradicts simulation rules | P1 |

### 1.6 Results & Export

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| EXP-01 | View results in workspace | Completed experiment | 1. Navigate to ResultsView tab<br>2. Observe charts and summary | Charts render (trajectory, bar chart, metric); AI summary displayed (if enabled) | Empty results, single round | P0 |
| EXP-02 | CSV export | Completed experiment | 1. Click "Export"<br>2. Select "CSV" format<br>3. Confirm | CSV file downloaded with correct columns; all events included; scenario parameters present as columns | Large experiment (>100 events), special characters in data | P0 |
| EXP-03 | Data consistency: CSV vs in-browser | Completed experiment | 1. Export CSV<br>2. Parse CSV manually<br>3. Compare key values with in-browser ResultsView | Agent actions, rounds, and timestamps match between CSV and browser | — | P1 |
| EXP-04 | Markdown report | Completed experiment | 1. Click "Export"<br>2. Select "Markdown Report"<br>3. Confirm | Report downloaded with structured sections; readable formatting | Very long experiment | P1 |
| EXP-05 | Data consistency: CSV vs Markdown vs JSON | Completed experiment | 1. Export all three formats<br>2. Compare data across formats | Same agent actions, rounds, and outcomes present in all formats | — | P1 |
| EXP-06 | Branch comparison | Experiment with ≥2 branches | 1. Select branch A<br>2. Select branch B<br>3. Click "Compare" | Visual comparison shown (side-by-side or overlay); key metrics highlighted | Branches of different lengths, empty branches | P0 |

### 1.7 Branch Management

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| BRN-01 | Create branch from node | Experiment with at least one completed node | 1. Select a completed node<br>2. Click "Branch from here"<br>3. Name the branch | New branch created; separate from trunk; both visible in tree | Branch from root, branch from leaf | P0 |
| BRN-02 | Compare two branches | ≥2 branches exist | 1. Select branch A and branch B<br>2. View comparison | Differences highlighted; both trees navigable | Branches with identical content | P0 |
| BRN-03 | Merge/sync branches | Two divergent branches | 1. Click "Merge" on target branch<br>2. Confirm | Node data merged; conflicts handled or flagged | Unmergeable branches, circular dependencies | P1 |

---

## Phase 2: Edge Cases & Error Handling (Days 5-6 — 2026-07-14 to 2026-07-15)

### 2.1 Invalid Inputs

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| ERR-01 | Malformed JSON in event creation | Experiment created | 1. Open New Event dialog<br>2. Paste malformed JSON in data field<br>3. Save | Validation error shown; event not created | SQL injection attempt in fields | P1 |
| ERR-02 | Empty fields in experiment creation | User at Create page | 1. Leave name empty<br>2. Try to create | Validation prevents submission; error message for required field | All fields empty | P0 |
| ERR-03 | Oversized data upload | — | 1. Upload a >100MB file | Error shown; file rejected; no crash | Very large text content | P1 |
| ERR-04 | Invalid agent names | Creating/modifying experiment | 1. Enter empty/very long/special character agent name | Validation blocks submission | Name collision detection | P1 |
| ERR-05 | Invalid round count | Creating experiment | 1. Enter 0 or negative rounds | Validation blocks; minimum 1 round enforced | Non-integer input | P1 |

### 2.2 Boundary Conditions

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| BND-01 | Maximum agents | — | 1. Create experiment with maximum supported agents<br>2. Try to add more | UI enforces max limit; performance acceptable at limit | — | P1 |
| BND-02 | Maximum rounds | — | 1. Create experiment with high round count (e.g., 50)<br>2. Run to completion | Executes without timeout; all rounds logged | — | P1 |
| BND-03 | Empty network | — | 1. Create experiment with 0 connections between agents | Simulation proceeds with isolated agents; no neighbour observations | — | P2 |
| BND-04 | Single agent | — | 1. Create experiment with 1 agent<br>2. Run | Agent makes decisions; no neighbour interactions | — | P1 |

### 2.3 Error States

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| ERR-06 | LLM provider failure | Provider goes down mid-simulation | 1. Start experiment<br>2. Kill LLM provider process<br>3. Observe | Visible error in UI (not just backend log); clear message about which provider failed | — | P0 |
| ERR-07 | Model not found | Experiment configured with unavailable model | 1. Create experiment<br>2. Run | Error surfaced in frontend; experiment does not silently hang | Model name typo | P0 |
| ERR-08 | Backend crash during simulation | Experiment running | 1. Kill backend process<br>2. Check frontend | Connection lost warning in UI; reconnection attempts visible | — | P0 |
| ERR-09 | Network timeout | Proxy configured with high latency | 1. Configure high-latency provider<br>2. Run simulation | Timeout handled gracefully; error shown; not a complete hang | — | P1 |
| ERR-10 | Database connection error | DB unavailable | 1. Stop database<br>2. Perform any DB operation | Clear error; no silent data loss | — | P1 |

### 2.4 Concurrency

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| CON-01 | Multiple experiments running | 2+ experiments created | 1. Start experiment A<br>2. Start experiment B<br>3. Observe both | Both advance independently; no state cross-contamination | Both using same provider queue | P1 |
| CON-02 | Rapid UI interactions | Experiment running | 1. Rapidly click Advance, Branch, Export in succession | No double-submission; queue handles sequential operations | — | P1 |
| CON-03 | Browser tab duplication | Experiment running | 1. Duplicate tab<br>2. Interact with both tabs | WebSocket connections handled; no duplicate operations | Close one tab mid-operation | P2 |

### 2.5 State Consistency

| # | Scenario | Preconditions | Steps | Expected Behaviour | Edge Cases | Priority |
|---|----------|---------------|-------|--------------------|------------|----------|
| CON-04 | Refresh during simulation | Experiment running | 1. Refresh the page | State restored from backend; no data loss; no phantom UI state | Refresh mid-round | P0 |
| CON-05 | Browser back/forward during wizard | Mid-wizard | 1. Click browser back<br>2. Click browser forward | Wizard state preserved; no blank page | Back after creation | P1 |
| CON-06 | Refresh during export | Export in progress | 1. Click Export<br>2. Refresh before complete | No partial export files visible in UI; clean state | — | P2 |

---

## Phase 3: Cross-Cutting Concerns (Day 7 — 2026-07-16)

### 3.1 Frontend/Backend Parameter Consistency

| # | Scenario | Steps | Expected Behaviour | Priority |
|---|----------|-------|--------------------|----------|
| PAR-01 | Scene defaults propagation | 1. Select a scene in creation wizard<br>2. Note default parameters shown<br>3. Inspect backend DB/scene config | Scene defaults in frontend match backend scene definition exactly | P0 |
| PAR-02 | Builder state → API payload | 1. Configure full experiment in wizard<br>2. Click Create<br>3. Compare builder state with API request body | Every parameter the builder tracks is included in the API call; no extra fields | P0 |
| PAR-03 | Round-trip parameter fidelity | 1. Create experiment with known params<br>2. Fetch experiment via API<br>3. Compare every param | All parameters survive DB round-trip unchanged in type and value | P1 |
| PAR-04 | Default value handling | 1. Skip optional parameters in wizard<br>2. Check what backend receives | Backend applies correct defaults; no empty/null where a default exists | P1 |

### 3.2 Runtime Error Visibility

| # | Scenario | Steps | Expected Behaviour | Priority |
|---|----------|-------|--------------------|----------|
| VIS-01 | Model timeout error | 1. Configure a provider/model that will time out<br>2. Run experiment | Error message appears in workspace UI (not just console/backend log); user can identify which agent/model failed | P0 |
| VIS-02 | Scene compilation error | 1. Configure experiment with invalid scene params<br>2. Run | Clear error in UI: "Scene X has invalid parameter Y" | P0 |
| VIS-03 | JSON parsing error | 1. Set up agent that returns malformed JSON<br>2. Run | Error shown with the malformed output; fallback behaviour indicated | P0 |
| VIS-04 | Provider auth error | 1. Use expired API key<br>2. Run experiment | Auth error visible; not a generic "experiment failed" | P1 |

### 3.3 Results Consistency

| # | Scenario | Steps | Expected Behaviour | Priority |
|---|----------|-------|--------------------|----------|
| RES-01 | Export format equivalence | 1. Export same data as CSV, JSON, and Markdown<br>2. Parse all three<br>3. Compare agent actions and round counts | Every agent action present in all three formats; no extra/dropped events | P1 |
| RES-02 | In-browser vs exported data | 1. View results in browser (charts/tables)<br>2. Export CSV<br>3. Compare specific data points | In-browser numbers match exported file values | P1 |
| RES-03 | Branch comparison accuracy | 1. Create two known-different branches<br>2. Use comparison view<br>3. Verify differences | All actual differences highlighted; no false positives/negatives | P1 |

### 3.4 Data Integrity

| # | Scenario | Steps | Expected Behaviour | Priority |
|---|----------|-------|--------------------|----------|
| INT-01 | Refresh during auto-advance | 1. Start experiment with auto-advance ON<br>2. Refresh page mid-advance<br>3. Check experiment state | No data loss; experiment continues from correct point; no duplicate nodes | P0 |
| INT-02 | Navigation away and back | 1. Start experiment<br>2. Navigate to Dashboard<br>3. Navigate back to experiment | All simulation data preserved; no phantom branches | P1 |
| INT-03 | Crash recovery | 1. Kill backend while experiment running<br>2. Restart backend<br>3. Check experiment state | Data persisted in DB; experiment resumable (or clearly stated as failed) | P1 |
| INT-04 | Branch data isolation | 1. Create two branches from same parent<br>2. Run different scenarios in each<br>3. Check data | Branch A's data does not appear in Branch B's results | P1 |

---

## Phase 4: Regression & Fix Verification (Days 8-9 — 2026-07-17 to 2026-07-18)

### 4.1 Re-run Failing Scenarios

After each bug fix, re-run the exact test scenario that revealed the bug. Document:

| Bug ID | Test Scenario | Initial Status | Re-run Status | Date Fixed |
|--------|---------------|----------------|---------------|------------|
| BUG-XXX | AUTH-01 | FAIL | PASS | YYYY-MM-DD |

### 4.2 Regression Check — Adjacent Modules

When a fix touches one module, re-run tests for all adjacent/connected modules:

| Fix Location | Adjacent Tests to Re-run |
|-------------|--------------------------|
| `simtree_runtime.py` | All SimTree tests, runner tests, advance tests |
| `export_service.py` | CSV export tests, results view tests, Markdown report tests |
| `experiment_runner.py` | Experiment creation tests, lifecycle tests |
| `frontend/components/workspace/` | Workspace component tests, integration tests |
| `frontend/services/` | Service tests, E2E tests |
| AI Scientist | AI Scientist tests, experiment creation tests, E2E health check |
| Auth | Auth tests, protected route tests, E2E smoke tests |
| Environment/Events | Environment tests, event injection tests, integration tests |

### 4.3 Full Beta Demo Script Smoke Test

Run the complete Beta demo flow end-to-end:

1. **Login** → Navigate to dashboard
2. **Create experiment** → Using AI Scientist with a social dilemma scenario
3. **Run simulation** → Let auto-advance complete at least 3 rounds
4. **Inject event** → Create and inject a timed environment event
5. **Create branch** → Branch from round 2, run alternative scenario
6. **Compare branches** → Use comparison view
7. **Export results** → CSV + Markdown
8. **Verify exports** → Cross-check data between formats

All 8 steps must pass without errors.

### 4.4 E2E Health Check Re-run

```bash
cd ~/Documents/ZJU\ work/fos/frontend
npx playwright test e2e/health-check.spec.ts --project=en 2>&1 | tee ../test_results/regression-health-en-$(date +%F).log
npx playwright test e2e/health-check.spec.ts --project=zh 2>&1 | tee ../test_results/regression-health-zh-$(date +%F).log
```

Compare with baseline from Phase 0 — any regression is a blocker.

---

## Phase 5: Final Pass & Stabilization (Day 10 — 2026-07-21)

### 5.1 Final P0 Test Run

Execute every P0 test case from Phases 1-3. All must pass. Document results:

```markdown
# Final Pass — P0 Test Results

**Date:** 2026-07-21

| ID | Description | Status | Notes |
|----|-------------|--------|-------|
| AUTH-01 | Register new user | PASS | — |
| AUTH-02 | Login with valid credentials | PASS | — |
| ... | ... | ... | ... |
```

### 5.2 Known Issues Document

Create `test_results/KNOWN_ISSUES.md` with:

```markdown
# Known Issues (Pre-Beta)

| ID | Description | Severity | Workaround | Planned Fix |
|----|-------------|----------|------------|-------------|
| ... | ... | P1 | ... | Post-Beta |
```

### 5.3 Handoff Document for Zheng Ziwei

Create `test_results/HANDOFF.md` with:

```markdown
# Test Handoff — Zheng Ziwei

**Date:** 2026-07-21
**From:** Justin Miller

## What Was Tested
[List all phases and modules tested]

## What's Known Broken
[List all OPEN bugs with reproduction steps]

## What's Fixed
[List all RESOLVED bugs with fix references]

## Remaining Risk Areas
[Features/modules with lower coverage]

## How to Run Tests
[Quick reference for test commands]

## Priority for Next Sprint
[What should be addressed first]
```

---

## Bug Tracking Template

Each bug entry in `BUG_LOG.md` should follow this structure:

```markdown
### BUG-NNN: [Title]

**Date found:** YYYY-MM-DD
**Severity:** P0 / P1 / P2
**Found by:** Justin / Zheng Ziwei
**Module:** [e.g., Experiment Creation → AI Scientist]

**Description:**
[Clear description of the bug]

**Steps to reproduce:**
1. [Step one]
2. [Step two]
3. [Step three]

**Expected:**
[What should happen]

**Actual:**
[What actually happens]

**Environment:**
- Browser: [name + version]
- Frontend commit: [hash]
- Backend commit: [hash]
- LLM provider: [name]

**Logs/Evidence:**
[Link to screenshot, HAR file, or console log]

**Status:** OPEN / IN PROGRESS / FIXED / WONTFIX
**Fixed by:** [Commit hash]
**Fix verified:** YYYY-MM-DD by [Name]
```

---

## Known pre-existing bugs (from codebase — START HERE)

The following real bugs have been identified in the codebase and should be logged
in `BUG_LOG.md` using the template above:

| Bug ID | Summary | Source File |
|--------|---------|-------------|
| BUG-UI-02 | System broadcasts appear exactly once with correct label | `tests/smoke_tests/test_ui_reliability.py` |
| BUG-UI-03 | SimTree renders reliably on Docker deployments | `tests/smoke_tests/test_ui_reliability.py` |
| BUG-CTX-01 | Agents had no prior-round context in council experiments | `src/fos/core/experiment/scenes/council_experiment.py:145` |
| BUG-CTX-03 | Token proactive refresh behaviour | `frontend/test/auth.proactiveRefresh.test.ts` |
| BUG-PGG-01 | Contributions are capped at agent's current token balance | `tests/integration/test_pgg_contribution_smoketest.py` |
| BUG-PGG-02 | Payoff calculations use constrained contribution values | `tests/integration/test_pgg_contribution_smoketest.py` |

---

## Cross-Testing with Tasks #1-#5

| Task | Cross-Test Requirement | When |
|------|------------------------|------|
| #1 — Setup environment | Use same Python 3.12 / Node 22 environment | Phase 0 |
| #2 — Parameter consistency | Verify every frontend param reaches backend unchanged | Phase 3 (PAR-01 to PAR-04) |
| #3 — Error visibility | Check errors surface in UI, not just backend logs | Phase 3 (VIS-01 to VIS-04) |
| #4 — Results consistency | Same data across CSV, JSON, Markdown, in-browser | Phase 3 (RES-01 to RES-03) |
| #5 — Runtime refactoring | Re-run all SimTree tests after refactoring | Phase 4 (regression check) |

---

## Test Execution Summary Template

After each day, update `test_results/DAILY_LOG.md`:

```markdown
## Day X — YYYY-MM-DD

**Phase:** [Phase name]

**Items tested:** [List of IDs]

**Passed:** N
**Failed:** N (see bugs: BUG-XXX, BUG-YYY)
**Blocked:** N (reason)

**New bugs found:** N
**Bugs fixed:** N

**Notes:**
- [Any observations, flaky tests, environment issues]
- [Items deferred to next day]

**Time spent:** X hours
```

---

## Quick Reference — Test Commands

```bash
# Backend tests (all)
cd ~/Documents/ZJU\ work/fos && source venv/bin/activate && python -m pytest tests/ -v

# Backend tests (specific module)
python -m pytest tests/core/experiment/ -v

# Frontend tests (all)
cd frontend && npm run test:run

# Frontend tests (watch mode)
cd frontend && npm run test

# E2E health check (English)
cd frontend && npx playwright test e2e/health-check.spec.ts --project=en

# E2E health check (Chinese)
cd frontend && npx playwright test e2e/health-check.spec.ts --project=zh

# E2E smoke tests
cd frontend && npm run test:e2e:smoke

# E2E specific test
cd frontend && npx playwright test e2e/css-fos-smoke.spec.ts

# Start backend (dev)
cd src && uvicorn fos.backend.main:app --reload --port 8000

# Start frontend (dev)
cd frontend && npm run dev
```

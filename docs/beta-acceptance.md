# Research Workflow Beta Acceptance Criteria

This document defines the shared bar for the next FOS beta. A beta build is not ready until every required item below is either passing or has an explicitly documented owner, risk, and follow-up date.

## 1. Development Baseline

Required:

- The beta development branch is known and current.
- Local setup instructions in `README.md`, `QUICKSTART.md`, `frontend/README.md`, and `.github/workflows/ci.yml` agree on Python 3.12, Node.js 22, and npm 10.
- Developers can install backend dependencies with:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-test.txt
pip install -e .
```

- Developers can install frontend dependencies with:

```bash
cd frontend
nvm use
npm ci
```

Acceptance evidence:

- The environment marker files exist: `.python-version`, `.node-version`, `.nvmrc`, and `frontend/.npmrc`.
- No documented command depends on Python 3.9 or an unspecified Node version.

## 2. CI And Deterministic Tests

Required CI-equivalent commands:

```bash
PYTHONPATH=src python -m pytest tests/ -q --no-header \
  --cov=fos.core \
  --cov-fail-under=58 \
  --ignore=tests/llm_prompt_testing \
  --ignore=tests/smoke_tests \
  --ignore=tests/integration/test_real_llm_phase1.py \
  --ignore=tests/integration/test_llm_action_selection.py \
  --ignore=tests/load

cd frontend
npm run test:run
npm run build
npm run test:e2e:smoke
cd ..

node --test tests/load/lib/loadUsers.test.mjs
```

Acceptance evidence:

- The CI workflow runs the same deterministic suite.
- Failing tests are not hidden by documentation. If a known failure remains, it is listed with owner and expected fix.
- Playwright diagnostics are uploaded on browser smoke failure.

## 3. Login And Provider Management

Required:

- A new or existing beta tester can register or log in without manual database edits.
- Settings expose provider creation, provider test, and provider activation/default selection where applicable.
- OpenAI-compatible, Gemini, and mock/local provider paths fail with clear messages when misconfigured.

Acceptance evidence:

- The beta demo script can complete the provider setup step.
- Provider/model used for AI summaries and exports is visible or recorded where relevant.

## 4. Experiment Creation

Required:

- Users can create an experiment from a preset without hidden parameter mismatches.
- AI Scientist draft flows either produce valid builder state or a typed validation error.
- Scenario parameters, agents, actions, network, and runtime settings are reviewable before launch.

Acceptance evidence:

- Builder tests and scenario parity checks pass or known exceptions are documented.
- Failed extraction never silently launches an invalid simulation.

## 5. Runtime And Branching

Required:

- The workspace shows the current node, branch path, logs, and run status.
- Users can advance the main branch and create or continue an intervention branch.
- Runtime failures are visible and recoverable enough for a demo.

Acceptance evidence:

- A completed main branch can be produced through the UI.
- Branch and node selection updates logs and results consistently.

## 6. Environment Event Workflow

Required:

- Users can generate or review environment suggestions from the current simulation context.
- Users can apply an environment event or host intervention to the intended branch.
- Applied events are recorded in logs or event records and remain inspectable.

Acceptance evidence:

- The beta demo script can apply one environment event without manual database edits.
- Baseline and intervention paths remain distinct after the event.

## 7. Results, Comparison, And Exports

Required:

- Results, CSV export, Markdown report, and AI summary share the same branch-filtered metrics pipeline as much as possible.
- Results exposes baseline/intervention branch comparison as a first-class workflow.
- AI summaries save the input snapshot, selected branch, provider/model, prompt, and generation time.
- Markdown reports include enough metadata to trace how the summary was generated.

Acceptance evidence:

- Results tests cover branch filtering, summary metadata, Markdown export, and comparison snapshots.
- Backend export tests cover default export compatibility and enhanced results export.
- Exported CSV and Markdown can be explained without reading app state from memory.

## 8. Documentation And Demo Readiness

Required:

- `README.md` describes the project, required versions, local setup, standard checks, and beta demo links.
- `QUICKSTART.md` gives the fastest reliable path from clone to local platform.
- `frontend/README.md` describes the real FOS frontend, not generic Vite template content.
- `docs/beta-demo.md` is the fixed demo path.
- This acceptance document is linked from the top-level docs.

Acceptance evidence:

- A new developer can start the platform and find the demo path from `README.md`.
- A reviewer can determine whether the beta build is complete by walking this document.

## 9. Final Beta Sign-Off

Before tagging or presenting a beta build, confirm:

- Deterministic CI is green on the beta branch.
- The fixed beta demo has been completed by at least one developer who did not author the latest feature changes.
- Any real-LLM or Ollama-only failures are separated from deterministic CI failures.
- Known limitations are written in the release notes or beta handoff notes.
- No demo step relies on private local files, hidden database state, or undocumented provider settings.

# FOS Beta Demo Script

This script is the fixed path every developer should be able to run before a beta handoff. It is written for a local demo using the standard backend and frontend dev servers.

## Purpose

Show the complete research workflow:

```text
login -> provider setup -> create experiment -> run main branch -> environment event -> compare branches -> export results
```

The demo must not require manual database edits or hidden seed data.

## Prerequisites

- Python 3.12 environment installed and active.
- Node.js 22 and npm 10 active in `frontend/`.
- Backend dependencies installed with `pip install -r requirements-test.txt` and `pip install -e .`.
- Frontend dependencies installed with `npm ci`.
- A reachable LLM provider. For a local deterministic demo, use Ollama through the OpenAI-compatible provider option.
- Optional: an existing admin account created through the normal app flow or `scripts/ensure_admin.py`.

## Start The Platform

Terminal 1, backend:

```bash
source .venv/bin/activate
export PYTHONPATH=src
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2, frontend:

```bash
cd frontend
nvm use
npm run dev
```

Open http://localhost:5173.

## Demo Path

### 1. Log In

1. Open the frontend.
2. Register or log in with a test account.
3. Confirm the dashboard loads and the main navigation is visible.

Expected result:

- The user reaches the authenticated dashboard without console-breaking errors.
- Session refresh does not immediately log the user out.

### 2. Configure Provider

1. Open Settings.
2. Go to LLM Providers.
3. Add a provider.
4. For a local Ollama demo, use:

| Field | Value |
|-------|-------|
| Label | `Ollama` |
| Provider | `OpenAI-compatible` |
| Model | `qwen3:4b` |
| Base URL | `http://localhost:11434/v1` |
| API Key | `dummy` |

5. Save and run the provider test.
6. Activate the provider if the UI offers an explicit active/default action.

Expected result:

- Provider test succeeds or returns a clear, actionable error.
- The selected provider is available to new experiments and report generation.

### 3. Create Experiment

1. Start a new simulation or experiment from the dashboard.
2. Choose a stable preset that supports fast demo turns, such as a public-goods or council-style experiment.
3. Review scenario parameters, agents, actions, and network settings.
4. Launch the experiment.

Expected result:

- The simulation workspace opens.
- The root or first active node is visible in the tree/path view.
- Agent and log panels can be opened without empty-state confusion.

### 4. Run Main Branch

1. In the simulation workspace, advance the current branch.
2. Wait for the run to finish.
3. Inspect logs and agent state.

Expected result:

- A completed child node appears.
- Logs show agent actions or dialogue tied to the selected branch.
- Runtime failures, if any, are visible in the UI rather than silent.

### 5. Generate And Apply Environment Event

1. Open the environment suggestion or host intervention area.
2. Generate an environment suggestion from the current context.
3. Review the event content, severity, and target branch.
4. Apply the event to create or affect an intervention path.
5. Advance the intervention branch after applying the event.

Expected result:

- The event is recorded in the UI.
- The intervention branch contains environment or host-intervention evidence in logs.
- The original baseline branch remains available for comparison.

### 6. Compare Branches

1. Open Analysis or Results.
2. Select the baseline branch.
3. Select the intervention branch.
4. Review unique event counts, agent-difference counts, and comparison summary.
5. Optionally open the dedicated comparison view for detailed event examples.

Expected result:

- Branch comparison loads without requiring manual node IDs.
- The UI distinguishes baseline evidence from intervention evidence.
- Comparison output is derived from visible backend comparison data.

### 7. Generate Results Summary

1. In Results, select the branch to analyze.
2. Click Generate analysis.
3. Wait for the AI summary.

Expected result:

- The summary appears in plain prose.
- The UI records the selected branch, model/provider, and generation time.
- The summary input is based on the same metrics shown in Results.

### 8. Export Results

1. Export CSV from Results.
2. Export the Markdown report.
3. Open the downloaded files.

Expected result:

- CSV includes branch-specific logs and reproducible result count columns when exported from Results.
- Markdown includes summary, metric final values, activity counts, branch comparison, and reproducibility metadata.
- Exported content can be understood without asking which branch/model/input produced it.

## Demo Reset

After the demo:

- Keep the created simulation if it is useful as a fixture.
- Otherwise archive or delete it through the normal UI.
- Do not reset the database manually unless the demo specifically targets setup recovery.

## Troubleshooting Checklist

- Backend syntax errors: confirm `python --version` is 3.12.
- Frontend install errors: confirm `node --version` is 22 and `npm --version` is 10.
- Provider errors: check model name, base URL, API key, and provider activation state.
- Branch comparison errors: confirm both selected nodes are backend numeric nodes.
- Empty exports: confirm the selected branch has completed logs before exporting.

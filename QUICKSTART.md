# FOS Platform — Quick Start

This guide is the shared baseline for all developers.

## Required Versions

| Tool | Version |
|------|---------|
| Python | 3.12 |
| Node.js | 22 |
| npm | 10 |

Version marker files are included at the repository root:

- `.python-version`
- `.node-version`
- `.nvmrc`

The beta development baseline is the `beta` branch. Start new beta work from that branch after syncing with the team.

## Backend Setup

### Step 1: Navigate to the repository

```bash
cd /path/to/fos
```

### Step 2: Create and activate Python 3.12 environment

macOS / Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Step 3: Install backend dependencies

```bash
pip install -r requirements-test.txt
pip install -e .
```

### Step 4: Configure environment variables

```bash
cp .env.example .env
```

Fill in required secrets in `.env`, especially:

- `FOS_JWT_SIGNING_KEY`
- `ADMIN_EMAIL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

Optional landing page video:

```bash
VITE_BILIBILI_VIDEO_BVID=BVxxxxxxxxx
```

Leave `VITE_BILIBILI_VIDEO_BVID` empty to hide the preview video.

### Step 5: Start backend server

macOS / Linux:

```bash
export PYTHONPATH=src
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Frontend Setup

Open a new terminal.

```bash
cd /path/to/fos/frontend
nvm use
npm ci
npm run dev
```

If you do not use `nvm`, install Node.js 22 with your preferred version manager before running `npm ci`.

## Access The Platform

Once both servers are running:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000/api |
| API Docs | http://localhost:8000/schema/swagger |

## Adding Ollama Model

### Step 1: Make sure Ollama is running

```bash
ollama serve
```

### Step 2: Go to the frontend

Open http://localhost:5173 in your browser.

### Step 3: Navigate to Settings -> LLM Providers

Click "Add Provider" and fill in:

| Field | Value |
|-------|-------|
| Label | `Ollama` |
| Provider | `OpenAI-compatible` |
| Model | `qwen3:4b` |
| Base URL | `http://localhost:11434/v1` |
| API Key | `dummy` |

### Step 4: Save

Click "Save" to add the provider.

## Standard Test Commands

Run the CI-equivalent deterministic suite:

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

The GitHub Actions workflow in `.github/workflows/ci.yml` runs the same deterministic command groups with Python 3.12 and Node.js 22.

For the full local suite, including long browser checks:

```bash
python scripts/run_full_tests.py
```

The full local suite runs all pytest tests plus the complete Playwright suite. It can require local model/provider setup that routine CI does not provision.

## Beta Demo And Acceptance

Use these documents before beta handoff or when onboarding a new developer:

- [Beta demo script](docs/beta-demo.md): fixed walkthrough covering login, provider setup, experiment creation, main-branch execution, environment event application, branch comparison, and CSV/Markdown export.
- [Beta acceptance criteria](docs/beta-acceptance.md): phase-level checklist for deciding whether the next beta build is ready.

## Troubleshooting

### Backend fails with syntax or typing errors

Confirm the active Python is 3.12:

```bash
python --version
```

### Frontend dependency install fails

Confirm the active Node.js version is 22:

```bash
node --version
npm --version
```

Then reinstall from the lockfile:

```bash
cd frontend
npm ci
```

## Stopping The Servers

Backend: press `Ctrl+C` in the backend terminal.

Frontend: press `Ctrl+C` in the frontend terminal.

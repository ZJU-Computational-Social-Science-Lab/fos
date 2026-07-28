# FOS Frontend

This is the React + TypeScript client for FOS, the Future of Society multi-agent social simulation platform.

The frontend owns the researcher-facing workflow: authentication, provider configuration, experiment creation, simulation workspace controls, branch comparison, environment-event review, results analysis, and report export. It talks to the Litestar backend at `/api`.

## Runtime Baseline

| Tool | Required version |
|------|------------------|
| Node.js | 22 |
| npm | 10 |

The repository root includes `.node-version` and `.nvmrc`. The frontend also enables `engine-strict=true` in `.npmrc`, so dependency installation fails early when the local Node/npm version is outside the beta baseline.

## Install

```bash
cd frontend
nvm use
npm ci
```

If you do not use `nvm`, install Node.js 22 with your preferred version manager and confirm:

```bash
node --version
npm --version
```

Use `npm ci`, not `npm install`, so dependencies come from `package-lock.json`.

## Local Development

Start the backend first from the repository root, then run:

```bash
cd frontend
npm run dev
```

The Vite dev server listens on http://localhost:5173 and expects the backend API at http://localhost:8000/api unless configured otherwise through the shared runtime settings.

Optional landing-page video configuration:

```bash
VITE_BILIBILI_VIDEO_BVID=BVxxxxxxxxx
```

Leave `VITE_BILIBILI_VIDEO_BVID` empty to hide the preview video.

## Main Product Areas

- `pages/`: top-level routes such as landing, dashboard, settings, simulation workspace, and experiment creation.
- `components/experiment/`: the structured experiment builder and scenario configuration controls.
- `components/workspace/`: the simulation workspace panels, branch path views, node details, and run controls.
- `components/results/`: results charts, branch comparison entry points, AI summary metadata, CSV export, and Markdown report export.
- `store/`: Zustand slices for simulations, logs, agents, providers, environment events, and experiment orchestration.
- `services/`: typed API clients for simulations, tree operations, providers, AI Scientist, uploads, data sources, and environment suggestions.
- `locales/`: English and Chinese UI strings. Add keys in both `en.json` and `zh.json`.

## Standard Checks

These commands match the frontend portion of CI:

```bash
npm run test:run
npm run build
npm run test:e2e:smoke
```

Use focused Vitest runs while developing:

```bash
npm test -- --run components/results/ResultsView.test.tsx
```

Run strict i18n checks after adding or renaming UI copy:

```bash
npm run test:i18n
```

## Beta Demo Touchpoints

The frontend must support the fixed beta demo path documented in [../docs/beta-demo.md](../docs/beta-demo.md):

1. Log in.
2. Configure and test an LLM provider.
3. Create an experiment.
4. Run the main branch.
5. Generate and apply an environment event.
6. Compare baseline and intervention branches.
7. Export CSV and Markdown reports with reproducibility metadata.

See [../docs/beta-acceptance.md](../docs/beta-acceptance.md) for the phase acceptance criteria that define when the next beta version is ready.

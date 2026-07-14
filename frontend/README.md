# FOS Frontend

React + TypeScript frontend for FOS.

## Required Runtime

- Node.js 22
- npm 10

The frontend has `engine-strict=true` in `.npmrc`, so dependency installation fails early when the local Node/npm version does not match the project baseline.

## Setup

```bash
nvm use
npm ci
```

If you do not use `nvm`, install Node 22 with your preferred version manager and confirm:

```bash
node --version
npm --version
```

## Local Development

```bash
npm run dev
```

The dev server listens on http://localhost:5173.

Optional video configuration:

```bash
VITE_BILIBILI_VIDEO_BVID=BVxxxxxxxxx
```

Leave `VITE_BILIBILI_VIDEO_BVID` empty to hide the landing page preview video.

## Test And Build Commands

```bash
npm run test:run
npm run build
npm run test:e2e:smoke
```

Use `npm ci`, not `npm install`, for reproducible dependency installs from `package-lock.json`.

/**
 * Playwright configuration for E2E health-check runner.
 *
 * Runs all 13 scenarios in two languages (English, Chinese) sequentially
 * with long timeouts for LLM calls. No retries — we want to see failures
 * as-is for diagnostics.
 *
 * Automatically starts both backend (uvicorn) and frontend (vite) servers
 * before tests and tears them down after. reuseExistingServer: true means
 * manually started servers are reused without double-starting.
 *
 * Exports: default (Playwright config)
 */

import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const repoRoot = resolve(__dirname, '..');

export default defineConfig({
  globalSetup: resolve(__dirname, 'e2e/global-setup.ts'),
  testDir: './e2e',
  fullyParallel: false,        // Sequential — LLM backend can't handle parallel
  retries: 0,                  // No retries — see failures as-is
  timeout: 300_000,            // 5 min per scenario (LLM × N agents × 3 rounds)
  expect: {
    timeout: 30_000,
  },
  reporter: [
    ['list'],
    ['json', { outputFile: 'e2e/collected-results/playwright-report.json' }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: resolve(repoRoot, 'start-backend-e2e.cmd'),
      cwd: repoRoot,
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      cwd: resolve(__dirname),
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
  projects: [
    {
      name: 'en',
      use: {
        browserName: 'chromium',
        locale: 'en',
      },
    },
    {
      name: 'zh',
      use: {
        browserName: 'chromium',
        locale: 'zh',
      },
    },
  ],
});

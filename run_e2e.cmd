@echo off
REM Run E2E tests (requires backend + frontend already running)
REM For real LLM tests: set FOS_TEST_REAL_LLM=1 before running
cd /d C:\Users\Justin\Documents\ZJU_Work\fos\frontend
npx playwright test --project=en %*

@echo off
:: Start the FOS backend for E2E testing.
:: Activates the socialsim conda environment and runs uvicorn.
:: Used by Playwright webServer — must stay running until killed.
set PYTHONPATH=.
call conda activate socialsim
python -m uvicorn fos.backend.main:app --host 127.0.0.1 --port 8000

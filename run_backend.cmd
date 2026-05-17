@echo off
cd /d C:\Users\Justin\Documents\ZJU_Work\fos
call conda activate socialsim
set PYTHONPATH=C:\Users\Justin\Documents\ZJU_Work\fos\src
uvicorn fos.backend.main:app --reload --host 0.0.0.0 --port 8000

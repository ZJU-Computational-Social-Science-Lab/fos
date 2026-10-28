#!/bin/bash
# Runs the full Stage 9 regression pipeline once, strictly in order, from the
# prepared inputs through the fitted models, effect tables and written reports.
# Prerequisite: ANALYSIS_TABLE.csv and EXPERIMENT_FEATURES.csv must already exist
# in this directory (they are built by build_analysis_table.py / prep_features.py
# from frozen earlier-stage data and are NOT rebuilt here).
set -e
cd "$(dirname "$0")"
V="/home/justin/Documents/ZJU work/fos/venv/bin/python"
"$V" scripts/fit_models.py --model a --tag mainA
"$V" scripts/fit_models.py --model b --tag mainB
"$V" scripts/make_outputs.py
"$V" scripts/run_sensitivities.py all
"$V" scripts/make_reports.py
echo PIPELINE_DONE

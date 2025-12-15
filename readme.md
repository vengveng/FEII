# FEII — Replication Code (Problem Set 1)

This repository contains the code used to process bank Call Reports data, run the regression specifications in **R**, and generate publication-ready **LaTeX** tables used in `report.tex` / `report.pdf`.

## Repository structure

.
├── 1_process_data.py
├── 2_regressALL.r
├── 3_make_latex.py
├── helper_functions.py
├── data
│   ├── processed
│   │   ├── fed_funds_rate_quarterly.csv
│   │   ├── int_convertible_columns.json
│   │   └── l1_herfdepcty.csv
│   └── raw
│       ├── DFEDTAR.csv
│       ├── DFEDTARL.csv
│       ├── DFEDTARU.csv
│       └── l1_herfdepcty.csv
├── tables
│   ├── t8_A_full_both_FEcomposite.tex
│   ├── t8_A_full_both_mainFE.tex
│   └── t8_A_full_both_noBankFE.tex
├── report.tex
└── report.pdf

## Data requirements

To run the pipeline end-to-end, you must provide the WRDS Call Reports Stata file:

- **Required input (not included):** `callreports_1976_2020_WRDS.dta`

Place it at the following path (create directories if needed):

- `data/raw/callreports_1976_2020_WRDS.dta`

Federal funds rate data is already provided in this repository (see `data/raw/DFEDTAR*.csv` and the processed quarterly series in `data/processed/`).

## Running the code (must be executed in order)

The scripts are numbered intentionally and should be run sequentially:

1. **`1_process_data.py`**  
   Performs **all data processing**. This script ingests the raw Call Reports file (plus the provided rate/HHI inputs), cleans and merges datasets, constructs regression variables, applies required data treatment, and writes processed outputs to `data/processed/` for downstream use.

2. **`2_regressALL.r`**  
   Runs **all regressions in R** using the processed datasets produced by step (1). The regression outputs are written to disk (and/or used to produce the initial table outputs consumed by the next step).

3. **`3_make_latex.py`**  
   Generates **improved LaTeX tables** from the raw R outputs.  
   **Important:** this script performs *no analysis of any kind*. Its sole purpose is formatting/cleaning regression output into high-quality LaTeX tables (saved under `tables/`).

## Notes

- If you run the scripts out of order, later steps may fail due to missing intermediate outputs.
- `report.tex` compiles the final write-up and includes the generated tables; `report.pdf` is the compiled output.

If anything in the pipeline is unclear or fails to run, feel free to contact me.
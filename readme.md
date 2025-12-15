# FEII — Replication Code (Problem Set 1)

This repository contains the code used to process bank Call Reports data, run the regression specifications in **R**, and generate the tables used in `report.pdf` / `all_tables.pdf`.

## Data requirements

To run the pipeline, you must provide the WRDS Call Reports Stata file:

- **Required input (not included):** `callreports_1976_2020_WRDS.dta`

Place it at the following path:

- `data/raw/callreports_1976_2020_WRDS.dta`

Federal funds rate data is already provided in this repository.

## Running the code (must be executed in order)

The scripts are numbered intentionally and should be run sequentially:

1. **`1_process_data.py`**  
   Performs all data processing. This script ingests the raw Call Reports file (plus the provided rate/HHI inputs), cleans and merges datasets, constructs regression variables, applies required data treatment, and writes processed outputs to `data/processed/` for downstream use.

2. **`2_regress.r`**  
   Runs all regressions in R using the processed datasets produced by step (1). The regression outputs are saved.

3. **`3_make_latex.py`**  
   Generates improved LaTeX tables from the raw R outputs.  
   Importantly, this script performs no analysis of any kind. Its sole purpose is formatting/cleaning regression output (saved under `tables/`).

If anything in the pipeline is unclear or fails to run, feel free to contact me.
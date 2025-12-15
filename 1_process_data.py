import pandas as pd
from pathlib import Path
import numpy as np

from helper_functions import convert_integer_columns, load_and_prepare_l1, get_ff_rate

# ----------------------------------------------------
# 0. File paths and constants
# ----------------------------------------------------

load_cr_path = Path("data/raw/callreports_1976_2020_WRDS.dta")
save_cr_path = Path("data/processed/callreports_1976_2020_WRDS.csv")

load_l1_path = Path("data/raw/l1_herfdepcty.csv")
save_l1_path = Path("data/processed/l1_herfdepcty.csv")

regression_data_path = Path("data/processed/regression_data.csv")

keep_cols = [
    # IDs / time
    "rssdid",
    "cert",
    "bhcid",
    "name",
    "chartertype",
    "dateq",
    "year",
    "quarter",

    # Balance sheet & components
    "assets",
    "liabilities",
    "deposits",
    "intexpdomdep",
    "savdep",
    "timedep",
    "cash",
    "securities",
    "loans",
    "reloans",
    "ciloans",
    "fedfundsrepoliab",
    "timedepge100k",
]

log_variables = [

    # Panel A
    "total_deposits",
    "savings_deposits",
    "time_deposits",
    "total_liabilities",
    "wholesale_funding",

    # Panel B
    "total_assets",
    "cash",
    "total_securities",
    "total_loans",
    "re_loans",
    "ci_loans",
]

# renaming for parity with table viii
rename_mapping = {
    "deposits": "total_deposits",
    "savdep": "savings_deposits",
    "timedep": "time_deposits",
    "liabilities": "total_liabilities",

    "assets": "total_assets",
    "securities": "total_securities",
    "loans": "total_loans",
    "reloans": "re_loans",
    "ciloans": "ci_loans",
}

# ----------------------------------------------------
# 1. Load and merge data
# ----------------------------------------------------

# cr = call reports, l1 = L1 Herfindahl data
cr = pd.read_stata(load_cr_path, columns=keep_cols)
cr = cr[cr.chartertype == 200.0]
# Fix incorrect cert to avoid cert-quarter duplicates
cr.loc[cr["rssdid"] == 3637685, "cert"] = 58647
# Truncate the sample but not fully for speed
cr = cr[(cr.year >= 1993) & (cr.year <= 2014)]

# The integer conversion was not necessary in retrospect
cr = convert_integer_columns(cr)
l1 = load_and_prepare_l1(load_l1_path)

cr = cr.merge(
    l1[["cert", "year", "quarter", "l1_herfdepcty"]],
    on=["cert", "year", "quarter"],
    how="left",
    # pandas doc: “one_to_one” or “1:1”: check if merge keys are unique in both left and right datasets.
    # It must be true that there is no duplication of the keys in either dataset.
    validate="1:1",
    indicator="_merge"
)

fund_rate = get_ff_rate()
cr = cr.merge(
    fund_rate[["year", "quarter", "FF", "d_FF"]],
    on=["year", "quarter"],
    how="left",
    # many cr rows per unique (year, quarter) in fund_rate
    validate="m:1",
)

# ----------------------------------------------------
# Minor diagnostics and saving intermediate files
# ----------------------------------------------------
# cr.to_csv(save_cr_path, index=False)
# l1.to_csv(save_l1_path, index=False)

# total_rows = len(cr)
# matched_missing = cr[(cr["_merge"] == "both") & (cr["l1_herfdepcty"].isna())]
# affected_certs = matched_missing["cert"].unique()
# total_certs = cr["cert"].nunique()
# print(f"Rows with l1 match but NaN herfdepcty: {len(matched_missing)} out of {total_rows} ({len(matched_missing) / total_rows:.2%}).")
# print(f"Unique certificates affected: {len(affected_certs)} out of {total_certs} ({len(affected_certs) / total_certs:.2%}).")

# ----------------------------------------------------
# 2. Construct features
# ----------------------------------------------------

# Size indicators
# average assets per bank and quantiles
avg_assets = cr.groupby("rssdid")["assets"].mean()

q75 = avg_assets.quantile(0.75)
q90 = avg_assets.quantile(0.90)

size_df = avg_assets.to_frame("avg_assets").reset_index()
cr = cr.merge(size_df, on="rssdid", how="left")

#   Indicators for use in R
cr["top25_assets"] = (cr["avg_assets"] >= q75).astype(int)
cr["top10_assets"] = (cr["avg_assets"] >= q90).astype(int)

# Main regression features
cr = cr.sort_values(["rssdid", "dateq"])

cr['deposit_rate'] = 4 * cr['intexpdomdep'] / cr['deposits'] # yes
cr['d_deposit_rate'] = cr.groupby('rssdid')['deposit_rate'].diff()
cr['d_deposit_spread'] = cr['d_FF'] - cr['d_deposit_rate']

cr.rename(
    columns=rename_mapping,
    inplace=True,
)

cr["wholesale_funding"] = cr["total_liabilities"] - cr["total_deposits"]

# Growth indicators for R
growth_assets = cr.groupby("rssdid")["total_assets"].pct_change(fill_method=None)
cr["high_asset_growth"] = (growth_assets >= 1).fillna(False).astype(int)

# Log transformations and first differences
for variable in log_variables:
    cr[variable] = cr[variable].astype("float64")
    mask_bad = cr[variable] <= 0
    print(variable, "non-positive:", mask_bad.sum())
    cr.loc[mask_bad, variable] = np.nan

    cr[variable] = np.log(cr[variable])
    cr[f'd_{variable}'] = cr.groupby('rssdid')[variable].diff()
    cr.drop(columns=[variable], inplace=True)

# Post 2008 dummy
cr['post2008'] = (cr['year'] >= 2009).astype(int)

# Trim to regression sample and save
cr = cr[(cr.year >= 1994) & (cr.year <= 2013)]
print(cr)
print(cr[["d_deposit_rate", "d_FF", "d_deposit_spread", "post2008"]])
cr.to_csv(regression_data_path, index=False)
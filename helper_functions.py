import json
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_integer_dtype
from tqdm import tqdm

def is_integer_convertible(col: pd.Series) -> bool:
    """
    A column is 'int-convertible' if:
    - it's numeric (float or int-like), and
    - all non-NaN entries are whole numbers (end with .0 in float representation).
    NaNs are allowed.
    """

    if is_integer_dtype(col):
        return False
    if not is_numeric_dtype(col):
        return False
    s = col.dropna()

    if s.empty:
        return False

    s = s.astype("float64")

    # Check: value == round(value) for all non-NaN entries
    return np.all(np.isfinite(s)) and np.all(np.isclose(s, np.round(s), rtol=0))

def convert_integer_columns(df: pd.DataFrame) -> pd.DataFrame:

    integer_like_cols = [col for col in df.columns if is_integer_convertible(df[col])]

    out_path = Path("data/processed/int_convertible_columns.json")
    with out_path.open("w") as f:
        json.dump(integer_like_cols, f, indent=2)

    tqdm.write(f"Found {len(integer_like_cols)} integer columns.")

    df[integer_like_cols] = df[integer_like_cols].astype("Int64")
    df["cert"] = df["cert"].astype("Int64")
    df["year"] = df["year"].astype("Int64")
    df["quarter"] = df["quarter"].astype("Int64")
    return df

def load_and_prepare_l1(path: Path) -> pd.DataFrame:
    l1 = pd.read_csv(path)

    l1["year"] = l1["dateq"].str[:4].astype("Int64")
    l1["quarter"] = l1["dateq"].str[-1].astype("Int64")
    l1["cert"] = l1["cert"].astype("Int64")
    return l1


def get_ff_rate():
    path_ff_ = Path("data/raw/DFEDTAR.csv")
    path_ffl = Path("data/raw/DFEDTARL.csv")
    path_ffu = Path("data/raw/DFEDTARU.csv")

    ff_ = pd.read_csv(path_ff_, parse_dates=["observation_date"], index_col="observation_date")
    ffl = pd.read_csv(path_ffl, parse_dates=["observation_date"], index_col="observation_date")
    ffu = pd.read_csv(path_ffu, parse_dates=["observation_date"], index_col="observation_date")

    total_index = ff_.index.union(ffl.index)
    output = pd.DataFrame(index = total_index)
    output.loc[ff_.index, "FF"] = ff_["DFEDTAR"]
    output.loc[ffu.index, "FF"] = (ffu["DFEDTARU"] + ffl["DFEDTARL"]) / 2

    output.index = pd.to_datetime(output.index)
    # Resample to quarter end
    output = output.resample("QE").last()
    output["FF"] /= 100
    # d_FF = FF_t - FF_t-1
    output["d_FF"] = output["FF"].diff()

    output["year"] = output.index.year
    output["quarter"] = output.index.to_period("Q").quarter

    output.reset_index(inplace=True, drop=True)
    output.to_csv("data/processed/fed_funds_rate_quarterly.csv", index=False)
    
    return output
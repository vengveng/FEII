"""
This script is almost entirely AI-generated and performs only table
post-processing, not any statistical analysis. It reads the LaTeX tables
exported by the R regressions, cleans their formatting, and then builds 
composite tables across filters, fixed-effects specifications, and samples.
All coefficients and standard errors are taken as given from the input .tex
files; this script never re-estimates any model.

The correctness of the final tables was verified by comparing them to the 
original regression outputs. 
"""

from pathlib import Path
import re

# ============================================================
# Global config / paths
# ============================================================

BASE = Path("tables")

INTERACTION_LABEL = r"$\Delta FF_t \times$ Bank HHI"

# --------- Fix-tables config ---------

replacements_panelA = {
    r"d\_total\_deposits":    r"\makecell[c]{$\Delta$Total\\deposits}",
    r"d\_deposit\_spread":    r"\makecell[c]{$\Delta$Deposit\\spread}",
    r"d\_savings\_deposits":  r"\makecell[c]{$\Delta$Savings\\deposits}",
    r"d\_time\_deposits":     r"\makecell[c]{$\Delta$Time\\deposits}",
    r"d\_wholesale\_funding": r"\makecell[c]{$\Delta$Wholesale\\funding}",
    r"d\_total\_liabilities": r"\makecell[c]{$\Delta$Total\\liabilities}",
}

replacements_panelB = {
    r"d\_total\_assets":      r"\makecell[c]{$\Delta$Total\\assets}",
    r"d\_cash":               r"\makecell[c]{$\Delta$Cash}",
    r"d\_total\_securities":  r"\makecell[c]{$\Delta$Securities}",
    r"d\_total\_loans":       r"\makecell[c]{$\Delta$Total\\loans}",
    r"d\_re\_loans":          r"\makecell[c]{$\Delta$RE\\loans}",
    # r"d\_re\_loans":          r"\makecell[c]{$\Delta$Real\\estate\\loans}",
    r"d\_ci\_loans":          r"\makecell[c]{$\Delta$C\&I\\loans}",
}

FE_REPLACEMENTS = {
    "rssdid fixed effects":          "Bank f.e.",
    "rssdid-post2008 fixed effects": "Bank $\\times$ post-2008 f.e.",
    "dateq fixed effects":           "Quarter f.e.",
}

# --------- FE-composite config ---------

# Which sample/filter combo this FE composite is for
FE_SAMPLE_TAG = "full"
FE_FILTER_TAG = "both"

# fe_tag must match your R output filenames: t8_<panel>_<sample>_<filter>_<fe_tag>.tex
FE_SPECS = [
    ("mainFE",        True,  True,  True),   # rssdid + rssdid^post2008 + dateq
    ("noPost2008FE",  True,  True,  False),  # no post-2008 FE
    ("noBankFE",      False, True,  True),   # no bank FE
    ("noQuarterFE",   True,  False, True),   # no quarter FE
    ("onlyBankFE",    True,  False, False),  # only bank FE
    ("quarterOnlyFE", False, True,  False),  # only quarter FE
]

# --------- Filter-composite config (per sample) ---------

SAMPLES_FILTER = ["full", "pre2008", "top25", "top10"]
FILTERS = [
    ("none",   "None"),
    ("growth", "Growth"),
    ("winsor", "Winsor"),
    ("both",   r"\makecell{Growth+\\Winsor}"),
]

# --------- Robustness-composite config (across samples) ---------

SAMPLES_ROBUST = [
    ("full",    "Full sample"),
    ("pre2008", "Pre-2008"),
    ("top25",   "Top 25\\% assets"),
    ("top10",   "Top 10\\% assets"),
]
ROBUST_FILTER_TAG = "both"


# ============================================================
# 1. Fix tables (old 3fix_tables.py)
# ============================================================

def process_tex(path: Path, header_mapping: dict):
    lines = path.read_text().splitlines()

    new_lines = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            # skip the SE line after l1_herfdepcty
            skip_next = False
            continue

        # drop the level-term row + its SE line
        if (("l1\\_herfdepcty" in line or "l1_herfdepcty" in line)
                and "dFF" not in line):
            skip_next = True  # drop the SE line too
            continue

        # drop Within Adjusted R^2 row
        if "Within Adjusted R" in line or "Within R$^2$" in line:
            continue

        # drop fixed-effect lines
        if any(fe_label in line for fe_label in FE_REPLACEMENTS.keys()):
            continue

        new_lines.append(line)

    text = "\n".join(new_lines)

    # column headers
    for old, new in header_mapping.items():
        text = text.replace(old, new)

    # fixed effects labels
    for old, new in FE_REPLACEMENTS.items():
        text = text.replace(old, new)

    # rename interaction row
    text = text.replace(
        r"l1\_herfdepcty $\times$ dFF",
        r"$\Delta FF_t \times$ Bank HHI"
    )

    # change tabular to tabular* with stretch
    text = text.replace(
        r"\begin{tabular}{lcccccc}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccccc@{}}"
    )
    text = text.replace(
        r"\end{tabular}",
        r"\end{tabular*}"
    )

    # Standardize numeric formatting to 3 decimals
    pattern = re.compile(r"(-?\d+\.\d+)(?=(?:[^0-9]|$))")

    def pad_to_3_dec(match: re.Match) -> str:
        num_str = match.group(1)
        try:
            return f"{float(num_str):.3f}"
        except ValueError:
            return num_str

    text = pattern.sub(pad_to_3_dec, text)

    path.write_text(text)


def fix_all_tables():
    for tex_path in BASE.glob("*.tex"):
        name = tex_path.name

        if "panelA" in name or "A" in name:
            mapping = replacements_panelA
            panel_tag = "panelA"
        elif "panelB" in name or "B" in name:
            mapping = replacements_panelB
            panel_tag = "panelB"
        else:
            # skip any TeX files that aren't our panel tables
            continue

        print(f"Processing {name} with mapping {panel_tag}")
        process_tex(tex_path, mapping)

    print("All tables in 'tables/' cleaned and headers updated.")


# ============================================================
# Shared helper: parse LaTeX rows
# (used by all composite builders)
# ============================================================

def extract_values_from_row(line: str, skip_first: bool = True):
    """
    Parse a LaTeX row like:
      '   Observations & 4,848 & 4,848 & ...  \\\\'
    or
      '$\\Delta FF_t \\times$ Bank HHI & -1.555*** & 0.027 & ... \\\\'
    into a list of cell contents, optionally skipping the first label cell.

    Handles '\&' correctly by temporarily shielding it so we only split on
    real column separators '&'.
    """
    placeholder = "__AMP__PLACEHOLDER__"
    tmp = line.replace(r"\&", placeholder)

    parts = tmp.split("&")
    if skip_first:
        parts = parts[1:]

    vals = []
    for p in parts:
        p = p.rstrip()

        # remove only the *final* '\\' that ends the row
        if p.endswith(r"\\"):
            p = p[:-2].rstrip()

        # restore '\&'
        p = p.replace(placeholder, r"\&")

        p = p.strip()
        if p:
            vals.append(p)

    return vals


# ============================================================
# 2. FE composites (old 4_composite_tables_fe.py)
# ============================================================

def parse_panel_file_fe(path: Path):
    """
    From a single panel file (e.g. t8_A_full_both_mainFE.tex) extract:
      - header_vars: text of column headers (labels)
      - header_nums: column numbers (1), (2), ...
      - coefs:       coefficient cells on the interaction row
      - ses:         standard-error cells just below
    """
    text = path.read_text()
    lines = text.splitlines()

    # Header between \toprule and first \midrule
    top_idx = next(i for i, l in enumerate(lines) if r"\toprule" in l)
    mid_idx = next(i for i, l in enumerate(lines) if r"\midrule" in l and i > top_idx)
    header_lines = lines[top_idx + 1: mid_idx]  # typically 2 lines

    header_vars = extract_values_from_row(header_lines[0], skip_first=True)
    header_nums = extract_values_from_row(header_lines[1], skip_first=True)

    # Find interaction (coef) row robustly
    int_idx = None

    # (1) pretty label
    for i, l in enumerate(lines):
        if INTERACTION_LABEL in l:
            int_idx = i
            break

    # (2) fallback: original variable name patterns from fixest
    if int_idx is None:
        for i, l in enumerate(lines):
            if (
                ("l1\\_herfdepcty" in l or "l1_herfdepcty" in l)
                and ("dFF" in l or "d_FF" in l or " x dFF" in l or r"\times dFF" in l)
            ):
                int_idx = i
                break

    if int_idx is None:
        raise ValueError(f"Could not locate interaction row in {path}")

    coef_line = lines[int_idx]

    # SE row = first line after coef_line with '&'
    se_idx = None
    for j in range(int_idx + 1, len(lines)):
        L = lines[j]
        if "&" in L:
            se_idx = j
            break
    if se_idx is None:
        raise ValueError(f"Could not locate SE row in {path}")
    se_line = lines[se_idx]

    coefs = extract_values_from_row(coef_line, skip_first=True)
    ses = extract_values_from_row(se_line, skip_first=True)

    return header_vars, header_nums, coefs, ses


def build_composite_panel_fe(sample_tag: str, filter_tag: str, panel: str):
    """
    Build a composite FE table for a given sample/filter/panel.

    Reads:
      t8_<panel>_<sample_tag>_<filter_tag>_<fe_tag>.tex
    for all fe_tag in FE_SPECS, extracts the interaction coefficient + SE,
    and writes:
      t8_<panel>_<sample_tag>_<filter_tag>_FEcomposite.tex

    Layout:
      - 3 FE columns: Bank f.e., Quarter f.e., Bank × 2008 f.e.
      - then one column per dependent variable
      - rows = FE specs; cells = coef + SE (makecell), FE columns = “Y” or blank
      - NO Observations column
    """
    parsed = {}
    header_vars = None
    header_nums = None

    for fe_tag, *_ in FE_SPECS:
        src = BASE / f"t8_{panel}_{sample_tag}_{filter_tag}_{fe_tag}.tex"
        if not src.exists():
            raise FileNotFoundError(f"Missing source table: {src}")

        h_vars, h_nums, coefs, ses = parse_panel_file_fe(src)

        if header_vars is None:
            header_vars = h_vars
            header_nums = h_nums

        parsed[fe_tag] = {
            "coefs": coefs,
            "ses": ses,
        }

    # number of regression columns (variables)
    k = len(header_vars)
    # total columns = 3 FE indicator columns + k regression columns
    n_cols = 3 + k
    col_spec = "c" * n_cols

    # FE column headers (use makecell to stack nicely)
    bank_header = r"\makecell[c]{Bank\\f.e.}"
    quarter_header = r"\makecell[c]{Quarter\\f.e.}"
    post_header = r"\makecell[c]{Bank $\times$\\2008 f.e.}"

    out_lines = []
    out_lines.append(r"\begingroup")
    out_lines.append(r"\centering")
    out_lines.append(
        rf"\begin{{tabular*}}{{\textwidth}}{{@{{\extracolsep{{\fill}}}}{col_spec}@{{}}}}"
    )
    out_lines.append(r"   \toprule")

    # First header row: FE columns + variable labels
    h1_vars = " & ".join(header_vars)
    out_lines.append(
        f"   {bank_header} & {quarter_header} & {post_header} & {h1_vars}\\\\"
    )

    # Second header row: blanks under FE columns + (1) (2) ... under variables
    h2_nums = " & ".join(header_nums)
    out_lines.append(f"           &               &                    & {h2_nums}\\\\")

    out_lines.append(r"   \midrule")
    out_lines.append(
        rf"   \multicolumn{{{n_cols}}}{{c}}{{{INTERACTION_LABEL}}}\\"
    )
    out_lines.append(r"   \midrule")

    # Each FE spec is a row with three FE columns + coef/SE cells
    for fe_tag, bank_fe, quarter_fe, post_fe in FE_SPECS:
        info = parsed[fe_tag]
        coefs = info["coefs"]
        ses = info["ses"]

        bank_symbol = r"Y" if bank_fe else ""
        quarter_symbol = r"Y" if quarter_fe else ""
        post_symbol = r"Y" if post_fe else ""

        cells = []
        for c, s in zip(coefs, ses):
            cell = rf"\makecell{{{c} \\ {s}}}"
            cells.append(cell)

        row = (
            f"   {bank_symbol} & {quarter_symbol} & {post_symbol} & "
            + " & ".join(cells)
            + r"\\"
        )
        out_lines.append(row)

    out_lines.append(r"   \bottomrule")
    out_lines.append(r"\end{tabular*}")
    out_lines.append(r"\par\endgroup")

    out_text = "\n".join(out_lines)
    out_path = BASE / f"t8_{panel}_{sample_tag}_{filter_tag}_FEcomposite.tex"
    out_path.write_text(out_text)
    print("Wrote", out_path)


# ============================================================
# 3. Robustness composite across samples
#    (old 4_composite_tables_rob.py)
# ============================================================

def parse_panel_file_with_obs(path: Path):
    """
    From a single t8_*.tex panel file, extract:
      - header_vars: variable headers (ΔTotal deposits, etc.)
      - header_nums: (1), (2), ...
      - coefs:       ΔFF×HHI coefficient row
      - ses:         standard error row just below
      - obs:         Observations row
    """
    text = path.read_text()
    lines = text.splitlines()

    # Header between \toprule and first \midrule
    top_idx = next(i for i, l in enumerate(lines) if r"\toprule" in l)
    mid_idx = next(i for i, l in enumerate(lines) if r"\midrule" in l and i > top_idx)
    header_lines = lines[top_idx + 1: mid_idx]

    header_vars = extract_values_from_row(header_lines[0], skip_first=True)
    header_nums = extract_values_from_row(header_lines[1], skip_first=True)

    # Interaction row
    int_idx = next(
        i for i, l in enumerate(lines)
        if INTERACTION_LABEL in l
    )
    coef_line = lines[int_idx]

    # SE row = first row after interaction line with '&'
    se_idx = None
    for j in range(int_idx + 1, len(lines)):
        L = lines[j]
        if "&" in L:
            se_idx = j
            break
    if se_idx is None:
        raise ValueError(f"Could not locate SE row in {path}")
    se_line = lines[se_idx]

    # Observations row
    obs_idx = next(i for i, l in enumerate(lines) if "Observations" in l)
    obs_line = lines[obs_idx]

    coefs = extract_values_from_row(coef_line, skip_first=True)
    ses = extract_values_from_row(se_line, skip_first=True)
    obs = extract_values_from_row(obs_line, skip_first=True)

    return header_vars, header_nums, coefs, ses, obs


def build_composite_panel_samples(panel: str):
    """
    Build a composite robustness table for a given panel (A or B), stacking:
    full, pre2008, top25, top10 — all with ROBUST_FILTER_TAG = 'both'.

    Writes: tables/t8_<panel>_robustness_composite.tex
    """
    parsed = {}
    header_vars = None
    header_nums = None

    for tag, label in SAMPLES_ROBUST:
        src = BASE / f"t8_{panel}_{tag}_{ROBUST_FILTER_TAG}.tex"
        if not src.exists():
            raise FileNotFoundError(f"Missing source table: {src}")

        h_vars, h_nums, coefs, ses, obs = parse_panel_file_with_obs(src)

        if header_vars is None:
            header_vars = h_vars
            header_nums = h_nums

        parsed[tag] = {
            "label": label,
            "coefs": coefs,
            "ses": ses,
            "obs": obs,
        }

    # number of regression columns
    k = len(header_vars)
    # total columns = Sample + k vars + Obs.
    n_cols = k + 2
    col_spec = "l" + "c" * k + "c"

    out_lines = []
    out_lines.append(r"\begingroup")
    out_lines.append(r"\centering")
    out_lines.append(
        rf"\begin{{tabular*}}{{\textwidth}}{{@{{\extracolsep{{\fill}}}}{col_spec}@{{}}}}"
    )
    out_lines.append(r"   \toprule")

    # header row 1: Sample + variable labels + Obs.
    h1 = " & ".join(header_vars)
    out_lines.append(r"   Sample & " + h1 + r" & Obs.\\")
    # header row 2: (1), (2), ... + blank under Obs.
    h2 = " & ".join(header_nums)
    out_lines.append(r"          & " + h2 + r" & \\")

    out_lines.append(r"   \midrule")
    out_lines.append(
        rf"   \multicolumn{{{n_cols}}}{{c}}{{{INTERACTION_LABEL}}}\\"
    )
    out_lines.append(r"   \midrule")

    # data rows: one per sample
    for tag, label in SAMPLES_ROBUST:
        info = parsed[tag]
        coefs = info["coefs"]
        ses = info["ses"]
        obs = info["obs"]

        # obs should be identical across columns; take the first non-empty
        obs_vals = [o for o in obs if o]
        n_str = obs_vals[0] if obs_vals else ""

        cells = [
            rf"\makecell{{{c} \\ {s}}}"
            for c, s in zip(coefs, ses)
        ]

        row = "   " + label + " & " + " & ".join(cells) + f" & {n_str}\\\\"
        out_lines.append(row)

    out_lines.append(r"   \bottomrule")
    out_lines.append(r"\end{tabular*}")
    out_lines.append(r"\par\endgroup")

    out_text = "\n".join(out_lines)
    out_path = BASE / f"t8_{panel}_robustness_composite.tex"
    out_path.write_text(out_text)
    print("Wrote", out_path)


# ============================================================
# 4. Filter composite for each sample
#    (old 4_composite_tables.py)
# ============================================================

def build_composite_panel_filters(sample_tag: str, panel: str):
    """
    Build composite across filters (None / Growth / Winsor / Both)
    for a given sample and panel.

    Writes: tables/t8_<panel>_<sample_tag>_composite.tex
    """
    parsed = {}
    header_vars = None
    header_nums = None

    for f_tag, f_label in FILTERS:
        src = BASE / f"t8_{panel}_{sample_tag}_{f_tag}.tex"
        if not src.exists():
            raise FileNotFoundError(f"Missing source table: {src}")

        h_vars, h_nums, coefs, ses, obs = parse_panel_file_with_obs(src)

        if header_vars is None:
            header_vars = h_vars
            header_nums = h_nums

        parsed[f_tag] = {
            "label": f_label,
            "coefs": coefs,
            "ses": ses,
            "obs": obs,
        }

    # Number of regression columns (variables)
    k = len(header_vars)
    # Total columns = Filter + k variables + Observations
    n_cols = k + 2
    col_spec = "l" + "c" * k + "c"

    out_lines = []
    out_lines.append(r"\begingroup")
    out_lines.append(r"\centering")
    out_lines.append(
        rf"\begin{{tabular*}}{{\textwidth}}{{@{{\extracolsep{{\fill}}}}{col_spec}@{{}}}}"
    )
    out_lines.append(r"   \toprule")

    # First header row: Filter + variable labels + Observations
    h1 = " & ".join(header_vars)
    out_lines.append(f"   Filter & {h1} & Obs.\\\\")

    # Second header row: (1), (2), ... + blank under Observations
    h2 = " & ".join(header_nums)
    out_lines.append(f"          & {h2} & \\\\")

    out_lines.append(r"   \midrule")
    out_lines.append(
        rf"   \multicolumn{{{n_cols}}}{{c}}{{{INTERACTION_LABEL}}}\\"
    )
    out_lines.append(r"   \midrule")

    # Data rows: one per filter
    for f_tag, f_label in FILTERS:
        info = parsed[f_tag]
        coefs = info["coefs"]
        ses = info["ses"]
        obs = info["obs"]

        # Observations should be identical across columns within a row
        obs_vals = [o for o in obs if o]
        n_str = obs_vals[0] if obs_vals else ""

        cells = []
        for c, s in zip(coefs, ses):
            cell = rf"\makecell{{{c} \\ {s}}}"
            cells.append(cell)

        row = "   " + f_label + " & " + " & ".join(cells) + f" & {n_str}\\\\"
        out_lines.append(row)

    out_lines.append(r"   \bottomrule")
    out_lines.append(r"\end{tabular*}")
    out_lines.append(r"\par\endgroup")

    out_text = "\n".join(out_lines)
    out_path = BASE / f"t8_{panel}_{sample_tag}_composite.tex"
    out_path.write_text(out_text)
    print("Wrote", out_path)


# ============================================================
# 5. Orchestration
# ============================================================

if __name__ == "__main__":
    # 1) Clean/fix all base tables
    fix_all_tables()

    # 2) Build composites across filters, for each sample × panel
    for sample in SAMPLES_FILTER:
        for panel in ["A", "B"]:
            build_composite_panel_filters(sample, panel)

    # 3) Build FE composites for full/both (Panel A & B)
    for panel in ["A", "B"]:
        build_composite_panel_fe(FE_SAMPLE_TAG, FE_FILTER_TAG, panel)

    # 4) Build robustness composites across samples (full, pre2008, top25, top10)
    for panel in ["A", "B"]:
        build_composite_panel_samples(panel)
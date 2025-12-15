library(fixest)

# This script runs all Table 8 regressions and exports the LaTeX tables.
# The helper functions are defined so that:
#   * build_sample_df() applies the sample restrictions and filters
#     (full / pre2008 / top25 / top10, and none / growth / winsor / both)
#     in one place and returns a cleaned regression dataset.
#   * run_main_regression() takes a given dataset and fixed-effect specification,
#     runs the same regression for all dependent variables, and writes the
#     Panel A / Panel B LaTeX tables with consistent formatting.
#
# The loops at the end automate all combinations:
#   * The first set of loops runs Table 8 for every (sample, filter) pair and
#     stores the models in all_results, while writing t8_A_*.tex and t8_B_*.tex.
#   * The final loop reuses the same code but varies only the fixed-effect
#     specification on the full-sample, "both"-filter data to generate the
#     FE-robustness tables.

# ----------------------------------------------------
# 0. Paths, helpers, and data loading
# ----------------------------------------------------

reg_path <- "data/processed/regression_data.csv"
# reg_path <- "data/processed/regression_data_small.csv"

winsor_clip <- function(x, probs = c(0.01, 0.99)) {
  qs <- quantile(x, probs = probs, na.rm = TRUE)
  x <- pmin(pmax(x, qs[1]), qs[2])
  return(x)
}

cr <- read.csv(
  reg_path,
  stringsAsFactors = FALSE,
  check.names = FALSE  # keep original column names
)

# ----------------------------------------------------
# 1. Dependent variables and column sets
# ----------------------------------------------------

dependent_variables <- c(
  # Liabilities / funding (Panel A)
  "d_total_deposits",
  "d_deposit_spread",
  "d_savings_deposits",
  "d_time_deposits",
  "d_wholesale_funding",
  "d_total_liabilities",
  # Assets (Panel B)
  "d_total_assets",
  "d_cash",
  "d_total_securities",
  "d_total_loans",
  "d_re_loans",
  "d_ci_loans"
)

panelA_vars <- c(
  "d_total_deposits",
  "d_deposit_spread",
  "d_savings_deposits",
  "d_time_deposits",
  "d_wholesale_funding",
  "d_total_liabilities"
)

panelB_vars <- c(
  "d_total_assets",
  "d_cash",
  "d_total_securities",
  "d_total_loans",
  "d_re_loans",
  "d_ci_loans"
)

cols_for_sample <- c(dependent_variables, "l1_herfdepcty", "d_FF")

# Just to log the baseline intersection (like before)
mask_full <- complete.cases(cr[, cols_for_sample])
cat("Obs in intersection sample (full, none):", sum(mask_full), "\n")

# ----------------------------------------------------
# 2. Helpers: sample building + regression block
# ----------------------------------------------------

st_aer <- style.tex("aer")

build_sample_df <- function(cr, sample_tag, filter_tag) {
  df <- cr

  # ----- sample restriction -----
  # year, top25_assets, top10_assets were generated in python
  if (sample_tag == "pre2008") {
    df <- subset(df, year <= 2007)
  } else if (sample_tag == "top25") {
    if (!("top25_assets" %in% names(df))) {
      stop("Variable 'top25_assets' not found in regression_data. Create it in Python first.")
    }
    df <- subset(df, top25_assets == 1)
  } else if (sample_tag == "top10") {
    if (!("top10_assets" %in% names(df))) {
      stop("Variable 'top10_assets' not found in regression_data. Create it in Python first.")
    }
    df <- subset(df, top10_assets == 1)
  } else if (sample_tag != "full") {
    stop(paste("Unknown sample_tag:", sample_tag))
  }

  # ----- winsorization -----
  if (filter_tag %in% c("winsor", "both")) {
    for (v in dependent_variables) {
      df[[v]] <- winsor_clip(df[[v]])
    }
  }

  # ----- growth filter -----
  if (filter_tag %in% c("growth", "both")) {
    if (!("high_asset_growth" %in% names(df))) {
      stop("Variable 'high_asset_growth' not found in regression_data. Create it in Python first.")
    }
    df <- subset(df, is.na(high_asset_growth) | high_asset_growth == 0)
  }

  # ----- intersection sample (AFTER any winsor/filter) -----
  mask <- complete.cases(df[, cols_for_sample])
  cat("Obs in", sample_tag, "/", filter_tag, "intersection sample:", sum(mask), "\n")
  df <- df[mask, ]

  return(df)
}

run_main_regression <- function(df,
                                sample_tag,
                                filter_tag,
                                log_tag = NULL,
                                fe_spec = "rssdid + rssdid^post2008 + dateq",
                                fe_tag = NULL) {
  # ensure dFF alias exists for the interaction term
  if (!("dFF" %in% names(df)) && ("d_FF" %in% names(df))) {
    df$dFF <- df[["d_FF"]]
  }

  if (is.null(log_tag)) {
    log_tag <- paste0(sample_tag, " / ", filter_tag)
  }

  res <- list()

  for (y in dependent_variables) {
    fml <- as.formula(
      paste0(
        y,
        " ~ l1_herfdepcty + dFF:l1_herfdepcty | ", fe_spec
      )
    )

    m <- feols(
      fml,
      data    = df,
      cluster = ~ rssdid
    )

    cat("\n[", log_tag, "] Dependent variable:", y, "\n")
    print(summary(m))

    res[[y]] <- m
  }

  panelA_models <- res[panelA_vars]
  panelB_models <- res[panelB_vars]

  # ---------- file naming logic ----------
  # if fe_tag is NULL -> old names: t8_A_<sample>_<filter>.tex
  # if fe_tag is not NULL -> t8_A_<sample>_<filter>_<fe_tag>.tex
  if (is.null(fe_tag)) {
    file_A <- sprintf("tables/t8_A_%s_%s.tex", sample_tag, filter_tag)
    file_B <- sprintf("tables/t8_B_%s_%s.tex", sample_tag, filter_tag)
  } else {
    file_A <- sprintf("tables/t8_A_%s_%s_%s.tex", sample_tag, filter_tag, fe_tag)
    file_B <- sprintf("tables/t8_B_%s_%s_%s.tex", sample_tag, filter_tag, fe_tag)
  }

  etable(
    panelA_models,
    style.tex    = st_aer,
    digits       = 4,
    digits.stats = 3,
    se.below     = TRUE,
    fitstat      = ~ n + r2 + war2,
    file         = file_A
  )

  etable(
    panelB_models,
    style.tex    = st_aer,
    digits       = 4,
    digits.stats = 3,
    se.below     = TRUE,
    fitstat      = ~ n + r2 + war2,
    file         = file_B
  )

  invisible(res)
}

# ----------------------------------------------------
# 3. Run all sample/filter combinations
#     samples: full, pre2008, top25, top10
#     filters: none, growth, winsor, both
# ----------------------------------------------------

sample_tags <- c("full", "pre2008", "top25", "top10")
filter_tags <- c("none", "growth", "winsor", "both")

all_results <- list()

for (s in sample_tags) {
  all_results[[s]] <- list()

  for (f in filter_tags) {
    df_sf <- build_sample_df(cr, sample_tag = s, filter_tag = f)

    res_sf <- run_main_regression(
      df         = df_sf,
      sample_tag = s,
      filter_tag = f,
      log_tag    = paste0("Sample=", s, ", Filter=", f)
    )

    all_results[[s]][[f]] <- res_sf
  }
}


### Fixed effect variations
fe_variants <- c(
  mainFE        = "rssdid + rssdid^post2008 + dateq",  # baseline
  noBankFE      = "rssdid^post2008 + dateq",
  noQuarterFE   = "rssdid + rssdid^post2008",
  noPost2008FE  = "rssdid + dateq",
  onlyBankFE    = "rssdid",
  quarterOnlyFE = "dateq"
)

results_full_FE <- list()
df_sf <- build_sample_df(cr, sample_tag = "full", filter_tag = "both")

for (nm in names(fe_variants)) {
  fe_term <- fe_variants[[nm]]

  cat("\n======================================\n")
  cat("FE variant (full sample):", nm, " -> ", fe_term, "\n")
  cat("======================================\n")

  results_full_FE[[nm]] <- run_main_regression(
    df          = df_sf,
    sample_tag  = "full",
    filter_tag  = "both",
    fe_spec     = fe_term,
    fe_tag      = nm,
    log_tag     = paste0("FULL FE: ", nm)
  )
}
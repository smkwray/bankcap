"""First-pass descriptive diagnostics for the H.8 mechanism screen."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bankcap.io import read_csv, write_csv

OUTCOME_CHANGE_COLUMNS = [
    "d_securities_usd_millions",
    "d_deposits_usd_millions",
    "d_loans_usd_millions",
    "d_cash_assets_usd_millions",
    "d_securities_deposits_ratio",
    "d_cash_deposits_ratio",
    "d_loans_deposits_ratio",
]

CONTEXT_NUMERIC_COLUMNS = [
    "bill_share",
    "wam_months",
    "gross_issuance_usd",
    "liquidity_weighted_treasury_supply_usd",
    "tga_change_usd_millions",
]

EVENT_FLAGS = [
    "slr_relief_window",
    "rate_duration_shock_window",
    "banking_stress_2023_window",
    "large_tga_rebuild_window",
    "high_rate_regime",
]

TARGET_H8_GROUPS = {
    "large_domestic_banks",
    "small_domestic_banks",
    "foreign_related_institutions",
}

RELATIVE_BUCKET_SENSITIVITY_GRID = [
    (0.20, 0.80),
    (0.25, 0.75),
    (0.33, 0.67),
]


def bank_group_trends(panel: pd.DataFrame) -> pd.DataFrame:
    """Summarize levels and sample coverage by H.8 bank group."""

    rows: list[dict[str, object]] = []
    for group, gdf in panel.groupby("bank_group"):
        row: dict[str, object] = {
            "bank_group": group,
            "n_rows": len(gdf),
            "first_period": gdf["period"].min(),
            "last_period": gdf["period"].max(),
        }
        for column in [
            "securities_usd_millions",
            "deposits_usd_millions",
            "loans_usd_millions",
            "cash_assets_usd_millions",
            "securities_deposits_ratio",
            "cash_deposits_ratio",
            "loans_deposits_ratio",
        ]:
            if column in gdf.columns:
                row[f"mean_{column}"] = pd.to_numeric(gdf[column], errors="coerce").mean()
                row[f"last_{column}"] = pd.to_numeric(gdf[column], errors="coerce").iloc[-1]
        rows.append(row)
    return pd.DataFrame(rows)


def target_common_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Return periods where all target H.8 bank groups are observed."""

    if "period" not in panel.columns or "bank_group" not in panel.columns:
        return panel.iloc[0:0].copy()
    target = panel.loc[panel["bank_group"].astype(str).isin(TARGET_H8_GROUPS)].copy()
    group_counts = target.groupby("period")["bank_group"].nunique()
    common_periods = group_counts[group_counts == len(TARGET_H8_GROUPS)].index
    return target.loc[target["period"].isin(common_periods)].copy()


def context_bucket(panel: pd.DataFrame) -> pd.Series:
    """Return bill-heavy/coupon-heavy/mixed buckets for each row."""

    bill = panel.get("bill_heavy_month", pd.Series(False, index=panel.index)).fillna(False).astype(bool)
    coupon = panel.get("coupon_heavy_month", pd.Series(False, index=panel.index)).fillna(False).astype(bool)
    bucket = pd.Series("mixed_or_unclassified", index=panel.index)
    bucket.loc[bill] = "bill_heavy"
    bucket.loc[coupon] = "coupon_heavy"
    return bucket


def relative_bill_share_bucket(panel: pd.DataFrame) -> pd.Series:
    """Return relative high/low/middle bill-share buckets."""

    if "bill_share_bucket" in panel.columns:
        return panel["bill_share_bucket"].fillna("missing").astype(str)
    high = panel.get("high_bill_share_month", pd.Series(False, index=panel.index)).fillna(False).astype(bool)
    low = panel.get("low_bill_share_month", pd.Series(False, index=panel.index)).fillna(False).astype(bool)
    bucket = pd.Series("middle_bill_share", index=panel.index)
    bucket.loc[high] = "high_bill_share"
    bucket.loc[low] = "low_bill_share"
    return bucket


def sample_summary_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Summarize target-group coverage and context-bucket support."""

    frames = {
        "all_target_rows": panel.loc[
            panel.get("bank_group", pd.Series("", index=panel.index)).astype(str).isin(TARGET_H8_GROUPS)
        ],
        "common_target_periods": target_common_panel(panel),
    }
    rows: list[dict[str, object]] = []
    context_cols = [c for c in CONTEXT_NUMERIC_COLUMNS if c in panel.columns]
    for sample_name, sample in frames.items():
        if sample.empty:
            rows.append(
                {
                    "sample": sample_name,
                    "bank_group": "all_target_groups",
                    "n_rows": 0,
                    "n_periods": 0,
                    "first_period": "",
                    "last_period": "",
                    "bill_heavy_rows": 0,
                    "coupon_heavy_rows": 0,
                    "mixed_or_unclassified_rows": 0,
                    "context_complete_share": 0.0,
                }
            )
            continue
        work = sample.copy()
        work["treasury_context_bucket"] = context_bucket(work)
        work["relative_bill_share_bucket"] = relative_bill_share_bucket(work)
        for group_name, gdf in [("all_target_groups", work), *list(work.groupby("bank_group"))]:
            row: dict[str, object] = {
                "sample": sample_name,
                "bank_group": group_name,
                "n_rows": len(gdf),
                "n_periods": gdf["period"].nunique(),
                "first_period": gdf["period"].min(),
                "last_period": gdf["period"].max(),
                "bill_heavy_rows": int(gdf["treasury_context_bucket"].eq("bill_heavy").sum()),
                "coupon_heavy_rows": int(gdf["treasury_context_bucket"].eq("coupon_heavy").sum()),
                "mixed_or_unclassified_rows": int(
                    gdf["treasury_context_bucket"].eq("mixed_or_unclassified").sum()
                ),
                "high_bill_share_rows": int(gdf["relative_bill_share_bucket"].eq("high_bill_share").sum()),
                "low_bill_share_rows": int(gdf["relative_bill_share_bucket"].eq("low_bill_share").sum()),
                "middle_bill_share_rows": int(gdf["relative_bill_share_bucket"].eq("middle_bill_share").sum()),
                "context_complete_share": float(
                    gdf.get("is_context_complete", pd.Series(False, index=gdf.index)).mean()
                ),
            }
            for column in context_cols:
                row[f"{column}_nonmissing"] = int(pd.to_numeric(gdf[column], errors="coerce").notna().sum())
            rows.append(row)
    return pd.DataFrame(rows)


def tga_complete_target_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Return the common target-group sample with complete context rows."""

    common = target_common_panel(panel)
    if common.empty:
        return common
    if "is_context_complete" in common.columns:
        return common.loc[common["is_context_complete"].fillna(False).astype(bool)].copy()
    required = [c for c in CONTEXT_NUMERIC_COLUMNS if c in common.columns]
    if not required:
        return common.iloc[0:0].copy()
    return common.loc[common[required].notna().all(axis=1)].copy()


def bank_group_response_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Compare average bank-group changes across bill-heavy and coupon-heavy contexts."""

    df = panel.copy()
    df["treasury_context_bucket"] = context_bucket(df)
    value_cols = [c for c in OUTCOME_CHANGE_COLUMNS if c in df.columns]
    if not value_cols:
        return pd.DataFrame(columns=["bank_group", "treasury_context_bucket", "n_rows"])
    grouped = df.groupby(["bank_group", "treasury_context_bucket"], as_index=False)
    out = grouped[value_cols].mean()
    counts = grouped.size().rename(columns={"size": "n_rows"})
    return counts.merge(out, on=["bank_group", "treasury_context_bucket"], how="left")


def relative_bill_share_response_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Compare average bank-group changes across relative high/low bill-share buckets."""

    df = panel.copy()
    df["relative_bill_share_bucket"] = relative_bill_share_bucket(df)
    value_cols = [c for c in OUTCOME_CHANGE_COLUMNS if c in df.columns]
    if not value_cols:
        return pd.DataFrame(columns=["bank_group", "relative_bill_share_bucket", "n_rows"])
    grouped = df.groupby(["bank_group", "relative_bill_share_bucket"], as_index=False)
    out = grouped[value_cols].mean()
    counts = grouped.size().rename(columns={"size": "n_rows"})
    return counts.merge(out, on=["bank_group", "relative_bill_share_bucket"], how="left")


def relative_bill_share_contrast_table(
    common_response: pd.DataFrame,
    tga_response: pd.DataFrame,
) -> pd.DataFrame:
    """Compare high-minus-low relative bill-share responses across two samples."""

    rows: list[dict[str, object]] = []
    for sample_name, response in [
        ("common_target_periods", common_response),
        ("tga_complete_common_target_periods", tga_response),
    ]:
        if response.empty:
            continue
        for group, gdf in response.groupby("bank_group"):
            high = gdf.loc[gdf["relative_bill_share_bucket"].eq("high_bill_share")]
            low = gdf.loc[gdf["relative_bill_share_bucket"].eq("low_bill_share")]
            if high.empty or low.empty:
                continue
            high_row = high.iloc[0]
            low_row = low.iloc[0]
            for outcome in [c for c in OUTCOME_CHANGE_COLUMNS if c in response.columns]:
                diff = float(high_row[outcome] - low_row[outcome])
                rows.append(
                    {
                        "sample": sample_name,
                        "bank_group": group,
                        "outcome_change": outcome,
                        "high_bill_mean": float(high_row[outcome]),
                        "low_bill_mean": float(low_row[outcome]),
                        "high_minus_low": diff,
                        "high_n": int(high_row["n_rows"]),
                        "low_n": int(low_row["n_rows"]),
                    }
                )
    contrasts = pd.DataFrame(rows)
    if contrasts.empty:
        return contrasts
    common = contrasts.loc[contrasts["sample"].eq("common_target_periods")]
    tga = contrasts.loc[contrasts["sample"].eq("tga_complete_common_target_periods")]
    sign_map = {
        (row.bank_group, row.outcome_change): 0
        if row.high_minus_low == 0
        else (1 if row.high_minus_low > 0 else -1)
        for row in common.itertuples(index=False)
    }
    tga_sign_map = {
        (row.bank_group, row.outcome_change): 0
        if row.high_minus_low == 0
        else (1 if row.high_minus_low > 0 else -1)
        for row in tga.itertuples(index=False)
    }
    contrasts["same_sign_as_other_sample"] = contrasts.apply(
        lambda row: sign_map.get((row["bank_group"], row["outcome_change"]))
        == tga_sign_map.get((row["bank_group"], row["outcome_change"])),
        axis=1,
    )
    return contrasts


def _panel_with_relative_bill_share_cutoffs(
    panel: pd.DataFrame,
    *,
    low_quantile: float,
    high_quantile: float,
) -> pd.DataFrame:
    """Return a panel copy with relative bill-share buckets recomputed from supplied cutoffs."""

    out = panel.copy()
    if "bill_share" not in out.columns:
        out["high_bill_share_month"] = False
        out["low_bill_share_month"] = False
        out["bill_share_bucket"] = "missing"
        return out
    bill_share = pd.to_numeric(out["bill_share"], errors="coerce")
    periods = out["period"] if "period" in out.columns else pd.Series(out.index, index=out.index)
    period_bill_share = pd.DataFrame({"period": periods, "bill_share": bill_share})
    valid = period_bill_share.dropna(subset=["bill_share"]).drop_duplicates("period")["bill_share"]
    if valid.empty:
        out["high_bill_share_month"] = False
        out["low_bill_share_month"] = False
        out["bill_share_bucket"] = "missing"
        return out
    low_cut = float(valid.quantile(low_quantile))
    high_cut = float(valid.quantile(high_quantile))
    out["low_bill_share_month"] = bill_share <= low_cut
    out["high_bill_share_month"] = bill_share >= high_cut
    out["bill_share_bucket"] = "middle_bill_share"
    out.loc[out["low_bill_share_month"], "bill_share_bucket"] = "low_bill_share"
    out.loc[out["high_bill_share_month"], "bill_share_bucket"] = "high_bill_share"
    out.loc[bill_share.isna(), "bill_share_bucket"] = "missing"
    out["relative_low_bill_share_cutoff"] = low_cut
    out["relative_high_bill_share_cutoff"] = high_cut
    return out


def relative_bill_share_cutoff_sensitivity_table(
    panel: pd.DataFrame,
    *,
    quantile_grid: list[tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """Summarize support and sign stability across alternative relative bill-share cutoffs."""

    rows: list[dict[str, object]] = []
    grid = quantile_grid or RELATIVE_BUCKET_SENSITIVITY_GRID
    for low_q, high_q in grid:
        if low_q >= high_q:
            raise ValueError("Relative bill-share low quantile must be below high quantile")
        bucketed = _panel_with_relative_bill_share_cutoffs(
            panel,
            low_quantile=low_q,
            high_quantile=high_q,
        )
        common = target_common_panel(bucketed)
        tga = tga_complete_target_panel(bucketed)
        common_response = relative_bill_share_response_table(common)
        tga_response = relative_bill_share_response_table(tga)
        contrasts = relative_bill_share_contrast_table(common_response, tga_response)
        common_contrasts = contrasts.loc[contrasts["sample"].eq("common_target_periods")] if not contrasts.empty else contrasts
        level = (
            common_contrasts.loc[
                common_contrasts["outcome_change"].isin(
                    [
                        "d_securities_usd_millions",
                        "d_deposits_usd_millions",
                        "d_loans_usd_millions",
                        "d_cash_assets_usd_millions",
                    ]
                )
            ]
            if not common_contrasts.empty
            else common_contrasts
        )
        loans = (
            level.loc[level["outcome_change"].eq("d_loans_usd_millions")]
            if not level.empty
            else level
        )
        support = sample_summary_table(bucketed)
        common_all = support.loc[
            support["sample"].eq("common_target_periods")
            & support["bank_group"].eq("all_target_groups")
        ]
        if common_all.empty:
            high_rows = low_rows = middle_rows = 0
        else:
            support_row = common_all.iloc[0]
            high_rows = int(support_row.get("high_bill_share_rows", 0))
            low_rows = int(support_row.get("low_bill_share_rows", 0))
            middle_rows = int(support_row.get("middle_bill_share_rows", 0))
        low_cutoff = (
            float(bucketed["relative_low_bill_share_cutoff"].dropna().iloc[0])
            if "relative_low_bill_share_cutoff" in bucketed
            and bucketed["relative_low_bill_share_cutoff"].notna().any()
            else pd.NA
        )
        high_cutoff = (
            float(bucketed["relative_high_bill_share_cutoff"].dropna().iloc[0])
            if "relative_high_bill_share_cutoff" in bucketed
            and bucketed["relative_high_bill_share_cutoff"].notna().any()
            else pd.NA
        )
        rows.append(
            {
                "low_quantile": low_q,
                "high_quantile": high_q,
                "low_bill_share_cutoff": low_cutoff,
                "high_bill_share_cutoff": high_cutoff,
                "common_high_rows": high_rows,
                "common_low_rows": low_rows,
                "common_middle_rows": middle_rows,
                "stable_level_contrasts": int(level["same_sign_as_other_sample"].sum()) if not level.empty else 0,
                "total_level_contrasts": int(len(level)),
                "loan_growth_signs_stable": bool(
                    len(loans) and loans["same_sign_as_other_sample"].fillna(False).astype(bool).all()
                ),
                "claim_warning": "descriptive cutoff sensitivity; not causal absorption evidence",
            }
        )
    return pd.DataFrame(rows)


def correlation_table(panel: pd.DataFrame, *, min_obs: int = 4) -> pd.DataFrame:
    """Compute simple within-bank-group correlations between context variables and outcomes."""

    rows: list[dict[str, object]] = []
    for group, gdf in panel.groupby("bank_group"):
        for x in [c for c in CONTEXT_NUMERIC_COLUMNS if c in gdf.columns]:
            xvalues = pd.to_numeric(gdf[x], errors="coerce")
            for y in [c for c in OUTCOME_CHANGE_COLUMNS if c in gdf.columns]:
                yvalues = pd.to_numeric(gdf[y], errors="coerce")
                valid = xvalues.notna() & yvalues.notna()
                n = int(valid.sum())
                corr = np.nan
                if n >= min_obs and xvalues[valid].nunique() > 1 and yvalues[valid].nunique() > 1:
                    corr = float(xvalues[valid].corr(yvalues[valid]))
                rows.append(
                    {
                        "bank_group": group,
                        "context_variable": x,
                        "outcome_change": y,
                        "n_obs": n,
                        "correlation": corr,
                        "claim_warning": "descriptive correlation; not causal absorption evidence",
                    }
                )
    return pd.DataFrame(rows)


def guarded_regression_table(panel: pd.DataFrame, *, min_obs: int = 8) -> pd.DataFrame:
    """Run tiny OLS screens with an intercept using ``numpy.linalg.lstsq``.

    These are deliberately minimal and flagged as descriptive. They are useful for triage and tests,
    but a final empirical design should replace them with explicit econometric specifications.
    """

    rows: list[dict[str, object]] = []
    if "bill_share" not in panel.columns:
        return pd.DataFrame(rows)
    for group, gdf in panel.groupby("bank_group"):
        x = pd.to_numeric(gdf["bill_share"], errors="coerce")
        for ycol in [c for c in OUTCOME_CHANGE_COLUMNS if c in gdf.columns]:
            y = pd.to_numeric(gdf[ycol], errors="coerce")
            valid = x.notna() & y.notna()
            n = int(valid.sum())
            if n < min_obs or x[valid].nunique() < 2:
                rows.append(
                    {
                        "bank_group": group,
                        "outcome_change": ycol,
                        "n_obs": n,
                        "intercept": np.nan,
                        "bill_share_coef": np.nan,
                        "r_squared": np.nan,
                        "claim_warning": "insufficient observations for descriptive OLS",
                    }
                )
                continue
            xmat = np.column_stack([np.ones(n), x[valid].to_numpy(dtype=float)])
            yvec = y[valid].to_numpy(dtype=float)
            beta, *_ = np.linalg.lstsq(xmat, yvec, rcond=None)
            fitted = xmat @ beta
            ss_res = float(np.sum((yvec - fitted) ** 2))
            ss_tot = float(np.sum((yvec - yvec.mean()) ** 2))
            r2 = np.nan if ss_tot == 0 else 1 - ss_res / ss_tot
            rows.append(
                {
                    "bank_group": group,
                    "outcome_change": ycol,
                    "n_obs": n,
                    "intercept": float(beta[0]),
                    "bill_share_coef": float(beta[1]),
                    "r_squared": r2,
                    "claim_warning": "guarded descriptive OLS; no causal interpretation",
                }
            )
    return pd.DataFrame(rows)


def event_window_table(panel: pd.DataFrame, *, window: int = 3) -> pd.DataFrame:
    """Build a compact event-window table around starts of configured flags."""

    df = panel.copy()
    df["period_dt"] = pd.to_datetime(df["date"], errors="coerce")
    rows: list[dict[str, object]] = []
    available_flags = [flag for flag in EVENT_FLAGS if flag in df.columns]
    outcomes = [c for c in OUTCOME_CHANGE_COLUMNS if c in df.columns]
    for flag in available_flags:
        for group, gdf in df.sort_values("period_dt").groupby("bank_group"):
            flags = gdf[flag].fillna(False).astype(bool).to_numpy()
            starts = [idx for idx, val in enumerate(flags) if val and (idx == 0 or not flags[idx - 1])]
            for event_number, start_idx in enumerate(starts, start=1):
                for rel in range(-window, window + 1):
                    idx = start_idx + rel
                    if idx < 0 or idx >= len(gdf):
                        continue
                    row = gdf.iloc[idx]
                    record: dict[str, object] = {
                        "event_flag": flag,
                        "bank_group": group,
                        "event_number": event_number,
                        "relative_period": rel,
                        "period": row["period"],
                    }
                    for outcome in outcomes:
                        record[outcome] = row[outcome]
                    rows.append(record)
    return pd.DataFrame(rows)


def run_first_pass_diagnostics(
    panel_path: str | Path,
    output_dir: str | Path,
    *,
    event_window: int = 3,
) -> dict[str, Path]:
    """Write the seeded first-pass diagnostic tables."""

    panel = read_csv(panel_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "sample_summary": out_dir / "sample_summary.csv",
        "bank_group_trends": out_dir / "bank_group_trends.csv",
        "bank_group_response_table": out_dir / "bank_group_response_table.csv",
        "common_target_response_table": out_dir / "common_target_response_table.csv",
        "tga_complete_response_table": out_dir / "tga_complete_response_table.csv",
        "relative_bill_share_response_table": out_dir / "relative_bill_share_response_table.csv",
        "common_target_relative_bill_share_response_table": out_dir
        / "common_target_relative_bill_share_response_table.csv",
        "tga_complete_relative_bill_share_response_table": out_dir
        / "tga_complete_relative_bill_share_response_table.csv",
        "relative_bill_share_contrasts": out_dir / "relative_bill_share_contrasts.csv",
        "relative_bill_share_cutoff_sensitivity": out_dir / "relative_bill_share_cutoff_sensitivity.csv",
        "correlations": out_dir / "correlations.csv",
        "guarded_regressions": out_dir / "guarded_regressions.csv",
        "event_windows": out_dir / "event_windows.csv",
    }
    write_csv(sample_summary_table(panel), outputs["sample_summary"])
    write_csv(bank_group_trends(panel), outputs["bank_group_trends"])
    write_csv(bank_group_response_table(panel), outputs["bank_group_response_table"])
    write_csv(bank_group_response_table(target_common_panel(panel)), outputs["common_target_response_table"])
    write_csv(bank_group_response_table(tga_complete_target_panel(panel)), outputs["tga_complete_response_table"])
    write_csv(relative_bill_share_response_table(panel), outputs["relative_bill_share_response_table"])
    common_relative = relative_bill_share_response_table(target_common_panel(panel))
    tga_relative = relative_bill_share_response_table(tga_complete_target_panel(panel))
    write_csv(common_relative, outputs["common_target_relative_bill_share_response_table"])
    write_csv(tga_relative, outputs["tga_complete_relative_bill_share_response_table"])
    write_csv(relative_bill_share_contrast_table(common_relative, tga_relative), outputs["relative_bill_share_contrasts"])
    write_csv(relative_bill_share_cutoff_sensitivity_table(panel), outputs["relative_bill_share_cutoff_sensitivity"])
    write_csv(correlation_table(panel), outputs["correlations"])
    write_csv(guarded_regression_table(panel), outputs["guarded_regressions"])
    write_csv(event_window_table(panel, window=event_window), outputs["event_windows"])
    return outputs

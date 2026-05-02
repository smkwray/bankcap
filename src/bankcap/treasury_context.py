"""Build the first-pass Treasury financing and liquidity-plumbing context panel."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from bankcap.config import load_project_config
from bankcap.episodes import apply_calendar_windows, load_episode_config
from bankcap.io import read_csv, write_csv

CONTEXT_ALIASES = {
    "period": ["period", "month", "date", "week", "quarter"],
    "bill_share": [
        "bill_share",
        "basis_bill_share",
        "fixed_baseline_bill_share",
        "bill_issuance_share",
        "share_bills",
        "bills_share",
        "bill_share_by_accepted_amount",
        "raw_bill_share",
        "liquid_bill_share",
    ],
    "wam_months": [
        "wam_months",
        "basis_wam_months",
        "fixed_baseline_wam_months",
        "weighted_average_maturity_months",
        "raw_weighted_maturity_months",
        "liquid_weighted_maturity_months",
    ],
    "gross_issuance_usd": [
        "gross_issuance_usd",
        "total_issuance_usd",
        "issuance_usd",
        "gross_issuance",
        "total_issuance",
        "accepted_amount_sum",
        "offering_amount_sum",
    ],
    "bill_issuance_usd": [
        "bill_issuance_usd",
        "bills_issuance_usd",
        "bill_gross_issuance_usd",
        "gross_bill_issuance",
    ],
    "coupon_issuance_usd": [
        "coupon_issuance_usd",
        "coupons_issuance_usd",
        "coupon_gross_issuance_usd",
        "coupon_issuance",
    ],
    "liquidity_weighted_treasury_supply_usd": [
        "liquidity_weighted_treasury_supply_usd",
        "liquid_treasury_supply_usd",
        "liquidity_weighted_supply_usd",
        "fixed_baseline_liquid_supply_usd",
        "liquid_supply_usd",
        "liquid_treasury_supply",
    ],
    "tga_change_usd_millions": [
        "tga_change_usd_millions",
        "d_tga_usd_millions",
        "tga_delta_usd_millions",
        "tga_change",
        "d_tga",
    ],
    "policy_rate_pct": [
        "policy_rate_pct",
        "fed_funds_target_pct",
        "iorb_pct",
        "iorb_rate",
        "fed_funds",
        "effective_fed_funds_pct",
    ],
    "qt_qe_regime": ["qt_qe_regime", "qe_qt_regime", "balance_sheet_regime", "fed_balance_sheet_regime"],
    "high_rate_regime": ["high_rate_regime", "is_high_rate_regime"],
    "slr_relief_window": ["slr_relief_window", "is_slr_relief_window"],
    "rate_duration_shock_window": [
        "rate_duration_shock_window",
        "duration_shock_window",
        "rate_shock_window",
    ],
    "banking_stress_2023_window": ["banking_stress_2023_window", "banking_stress_window"],
    "large_tga_rebuild_window": ["large_tga_rebuild_window", "tga_rebuild_window"],
}

CONTEXT_COLUMNS = [
    "bill_share",
    "wam_months",
    "gross_issuance_usd",
    "bill_issuance_usd",
    "coupon_issuance_usd",
    "liquidity_weighted_treasury_supply_usd",
    "tga_change_usd_millions",
    "policy_rate_pct",
    "qt_qe_regime",
    "high_rate_regime",
    "slr_relief_window",
    "rate_duration_shock_window",
    "banking_stress_2023_window",
    "large_tga_rebuild_window",
]

BOOL_COLUMNS = [
    "high_rate_regime",
    "bill_heavy_month",
    "coupon_heavy_month",
    "high_bill_share_month",
    "low_bill_share_month",
    "slr_relief_window",
    "rate_duration_shock_window",
    "banking_stress_2023_window",
    "large_tga_rebuild_window",
]


def _find_column(df: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    lower_map = {column.lower(): column for column in df.columns}
    for alias in aliases:
        if alias in df.columns:
            return alias
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


def _period_from_series(series: pd.Series, frequency: str) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.isna().all():
        # Already looks like a period string.
        text = series.astype(str)
        if frequency == "monthly":
            return text.str.slice(0, 7)
        return text
    if frequency == "monthly":
        return parsed.dt.to_period("M").astype(str)
    if frequency == "weekly":
        return parsed.dt.strftime("%Y-%m-%d")
    return series.astype(str)


def _aggregate_buycurve_issuance(raw: pd.DataFrame) -> pd.DataFrame:
    if not {"month", "security_type", "accepted_amount_sum"}.issubset(raw.columns):
        return raw
    work = raw.copy()
    work["accepted_amount_sum"] = pd.to_numeric(work["accepted_amount_sum"], errors="coerce")
    work["weighted_maturity_years"] = pd.to_numeric(
        work.get("weighted_maturity_years"), errors="coerce"
    )
    work["is_bill"] = work["security_type"].astype(str).str.lower().eq("bill")
    grouped = work.groupby("month", as_index=False).agg(
        gross_issuance_usd=("accepted_amount_sum", "sum"),
        bill_issuance_usd=("accepted_amount_sum", lambda s: s[work.loc[s.index, "is_bill"]].sum()),
        coupon_issuance_usd=(
            "accepted_amount_sum",
            lambda s: s[~work.loc[s.index, "is_bill"]].sum(),
        ),
    )
    maturity = (
        work.dropna(subset=["weighted_maturity_years", "accepted_amount_sum"])
        .assign(weighted_maturity_amount=lambda x: x["weighted_maturity_years"] * x["accepted_amount_sum"])
        .groupby("month", as_index=False)
        .agg(weighted_maturity_amount=("weighted_maturity_amount", "sum"), weight=("accepted_amount_sum", "sum"))
    )
    grouped = grouped.merge(maturity, on="month", how="left")
    grouped["wam_months"] = grouped["weighted_maturity_amount"] / grouped["weight"] * 12
    grouped["bill_share"] = grouped["bill_issuance_usd"] / grouped["gross_issuance_usd"].replace({0: pd.NA})
    return grouped.drop(columns=["weighted_maturity_amount", "weight"])


def _select_tdcladder_measure(raw: pd.DataFrame) -> pd.DataFrame:
    if not {"weight_family", "supply_basis"}.issubset(raw.columns):
        return raw
    work = raw.copy()
    preferred = work[
        work["weight_family"].astype(str).eq("fixed_baseline")
        & work["supply_basis"].astype(str).eq("issuance_flow")
    ]
    if preferred.empty:
        preferred = work[work["weight_family"].astype(str).eq("fixed_baseline")]
    if preferred.empty:
        preferred = work
    out = preferred.copy()
    if "raw_bill_share" in out.columns and "bill_share" not in out.columns:
        out["bill_share"] = out["raw_bill_share"]
    if "raw_weighted_maturity_years" in out.columns and "wam_months" not in out.columns:
        out["wam_months"] = pd.to_numeric(out["raw_weighted_maturity_years"], errors="coerce") * 12
    if "liquid_treasury_supply" in out.columns and "liquidity_weighted_treasury_supply_usd" not in out.columns:
        out["liquidity_weighted_treasury_supply_usd"] = out["liquid_treasury_supply"]
    return out


def _prepare_context_source(raw: pd.DataFrame, source_name: str) -> pd.DataFrame:
    if source_name == "buycurve":
        return _aggregate_buycurve_issuance(raw)
    if source_name == "tdcladder":
        return _select_tdcladder_measure(raw)
    if source_name == "liqsub" and "d_tga" not in raw.columns and "tga" in raw.columns:
        out = raw.copy()
        out["d_tga"] = pd.to_numeric(out["tga"], errors="coerce").diff()
        return out
    return raw


def _standardize_context_frame(
    path: str | Path,
    *,
    source_name: str,
    frequency: str,
) -> pd.DataFrame:
    raw = _prepare_context_source(read_csv(path), source_name)
    period_col = _find_column(raw, CONTEXT_ALIASES["period"])
    if period_col is None:
        raise ValueError(f"{source_name} context file has no period column: {path}")

    out = pd.DataFrame()
    out["period"] = _period_from_series(raw[period_col], frequency)
    for target in CONTEXT_COLUMNS:
        col = _find_column(raw, CONTEXT_ALIASES[target])
        if col is not None:
            out[target] = raw[col]
    out[f"source_{source_name}"] = True
    return out.drop_duplicates("period", keep="last")


def _coalesce_merge(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        raise ValueError("At least one context source file is required")
    merged = frames[0].copy()
    for idx, frame in enumerate(frames[1:], start=1):
        merged = merged.merge(frame, on="period", how="outer", suffixes=("", f"__{idx}"))
        for column in list(merged.columns):
            if "__" not in column:
                continue
            base = column.split("__", 1)[0]
            if base not in merged.columns:
                merged = merged.rename(columns={column: base})
            else:
                merged[base] = merged[base].combine_first(merged[column])
                merged = merged.drop(columns=[column])
    return merged


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _add_derived_context(
    df: pd.DataFrame,
    *,
    thresholds: dict[str, float] | None = None,
    episodes_config: dict | None = None,
) -> pd.DataFrame:
    thresholds = thresholds or {}
    out = df.copy()
    out["date"] = out["period"].map(lambda p: pd.Period(str(p)[:7], freq="M").to_timestamp("M"))
    out["frequency"] = "monthly"

    for numeric in [
        "bill_share",
        "wam_months",
        "gross_issuance_usd",
        "bill_issuance_usd",
        "coupon_issuance_usd",
        "liquidity_weighted_treasury_supply_usd",
        "tga_change_usd_millions",
        "policy_rate_pct",
    ]:
        if numeric in out.columns:
            out[numeric] = pd.to_numeric(out[numeric], errors="coerce")

    if "bill_share" not in out.columns and {"bill_issuance_usd", "gross_issuance_usd"}.issubset(out):
        denom = out["gross_issuance_usd"].replace({0: pd.NA})
        out["bill_share"] = out["bill_issuance_usd"] / denom
    if "coupon_share" not in out.columns:
        out["coupon_share"] = 1 - out["bill_share"] if "bill_share" in out.columns else pd.NA

    bill_cut = float(thresholds.get("bill_heavy_min_bill_share", 0.60))
    coupon_cut = float(thresholds.get("coupon_heavy_max_bill_share", 0.40))
    if "bill_share" in out.columns:
        out["bill_heavy_month"] = out["bill_share"] >= bill_cut
        out["coupon_heavy_month"] = out["bill_share"] <= coupon_cut
        valid_bill_share = out["bill_share"].dropna()
        if valid_bill_share.empty:
            out["high_bill_share_month"] = False
            out["low_bill_share_month"] = False
            out["bill_share_bucket"] = "missing"
        else:
            low_q = float(thresholds.get("low_bill_share_quantile", 0.25))
            high_q = float(thresholds.get("high_bill_share_quantile", 0.75))
            low_cut = valid_bill_share.quantile(low_q)
            high_cut = valid_bill_share.quantile(high_q)
            out["low_bill_share_month"] = out["bill_share"] <= low_cut
            out["high_bill_share_month"] = out["bill_share"] >= high_cut
            out["bill_share_bucket"] = "middle_bill_share"
            out.loc[out["low_bill_share_month"], "bill_share_bucket"] = "low_bill_share"
            out.loc[out["high_bill_share_month"], "bill_share_bucket"] = "high_bill_share"
            out.loc[out["bill_share"].isna(), "bill_share_bucket"] = "missing"
    else:
        out["bill_heavy_month"] = False
        out["coupon_heavy_month"] = False
        out["high_bill_share_month"] = False
        out["low_bill_share_month"] = False
        out["bill_share_bucket"] = "missing"

    for column in [
        "slr_relief_window",
        "rate_duration_shock_window",
        "banking_stress_2023_window",
        "large_tga_rebuild_window",
        "high_rate_regime",
    ]:
        if column in out.columns:
            out[column] = _as_bool(out[column])
        else:
            out[column] = False

    if episodes_config:
        out = apply_calendar_windows(out, episodes_config.get("calendar_windows", {}), period_col="period")

    if "tga_change_usd_millions" in out.columns:
        rebuild_cut = float(thresholds.get("large_tga_rebuild_min_change_usd_millions", 100000))
        out["large_tga_rebuild_window"] = out["large_tga_rebuild_window"].astype(bool) | (
            out["tga_change_usd_millions"] >= rebuild_cut
        )

    if "policy_rate_pct" in out.columns:
        high_rate_cut = float(thresholds.get("high_rate_min_policy_rate_pct", 4.0))
        out["high_rate_regime"] = out["high_rate_regime"].astype(bool) | (
            out["policy_rate_pct"] >= high_rate_cut
        )

    if "qt_qe_regime" not in out.columns:
        qt = out.get("qt_regime_window", pd.Series(False, index=out.index)).astype(bool)
        qe = out.get("qe_regime_window", pd.Series(False, index=out.index)).astype(bool)
        out["qt_qe_regime"] = "neutral"
        out.loc[qt, "qt_qe_regime"] = "QT"
        out.loc[qe, "qt_qe_regime"] = "QE"
    else:
        out["qt_qe_regime"] = out["qt_qe_regime"].fillna("unknown").astype(str)

    for column in BOOL_COLUMNS:
        if column not in out.columns:
            out[column] = False
        out[column] = out[column].fillna(False).astype(bool)

    source_cols = [c for c in out.columns if c.startswith("source_")]
    if source_cols:
        out["context_source_notes"] = out[source_cols].apply(
            lambda row: ",".join(c.replace("source_", "") for c, value in row.items() if bool(value)),
            axis=1,
        )
    else:
        out["context_source_notes"] = ""
    return out


def build_treasury_context(
    *,
    buycurve_path: str | Path | None = None,
    tdcladder_path: str | Path | None = None,
    liqsub_path: str | Path | None = None,
    output_path: str | Path | None = None,
    frequency: str = "monthly",
    project_config_path: str | Path | None = "config/project.yaml",
    episodes_config_path: str | Path | None = "config/episodes.yaml",
    thresholds: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Build a canonical Treasury context panel from imported sibling outputs."""

    frequency = frequency.lower()
    if frequency != "monthly":
        raise NotImplementedError("The seeded Treasury context builder currently supports monthly context")

    frames: list[pd.DataFrame] = []
    if buycurve_path is not None:
        frames.append(_standardize_context_frame(buycurve_path, source_name="buycurve", frequency=frequency))
    if tdcladder_path is not None:
        frames.append(_standardize_context_frame(tdcladder_path, source_name="tdcladder", frequency=frequency))
    if liqsub_path is not None:
        frames.append(_standardize_context_frame(liqsub_path, source_name="liqsub", frequency=frequency))

    cfg_thresholds: dict[str, float] = {}
    if project_config_path is not None and Path(project_config_path).exists():
        cfg_thresholds = load_project_config(project_config_path).get("thresholds", {}) or {}
    if thresholds:
        cfg_thresholds.update(thresholds)

    episodes = None
    if episodes_config_path is not None and Path(episodes_config_path).exists():
        episodes = load_episode_config(episodes_config_path)

    context = _coalesce_merge(frames)
    context = _add_derived_context(context, thresholds=cfg_thresholds, episodes_config=episodes)

    ordered = [
        "period",
        "date",
        "frequency",
        "bill_share",
        "coupon_share",
        "wam_months",
        "gross_issuance_usd",
        "liquidity_weighted_treasury_supply_usd",
        "tga_change_usd_millions",
        "qt_qe_regime",
        "high_rate_regime",
        "bill_heavy_month",
        "coupon_heavy_month",
        "high_bill_share_month",
        "low_bill_share_month",
        "bill_share_bucket",
        "slr_relief_window",
        "rate_duration_shock_window",
        "banking_stress_2023_window",
        "large_tga_rebuild_window",
        "context_source_notes",
    ]
    for column in ordered:
        if column not in context.columns:
            context[column] = pd.NA if column not in BOOL_COLUMNS else False
    context = context[ordered].sort_values("period").reset_index(drop=True)
    if output_path is not None:
        write_csv(context, output_path)
    return context

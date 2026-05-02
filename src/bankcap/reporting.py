"""Go/no-go reporting for the H.8 bank-group screen."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bankcap.diagnostics import target_common_panel, tga_complete_target_panel
from bankcap.io import ensure_parent, read_csv

CLAIM_BOUNDARY_TEXT = """\
## Claim boundary

This report is a mechanism screen, not bank-level identification. H.8 bank-group data cannot support
claims about individual-bank heterogeneity, merger-adjusted bank behavior, bank-level duration
exposure, or causal absorption. H.8 securities should be labeled as an aggregate that may combine
Treasury and agency securities unless a source-specific mapping proves otherwise.
"""

TARGET_H8_GROUPS = {
    "large_domestic_banks",
    "small_domestic_banks",
    "foreign_related_institutions",
}

LEVEL_OUTCOME_COLUMNS = [
    "d_securities_usd_millions",
    "d_deposits_usd_millions",
    "d_loans_usd_millions",
    "d_cash_assets_usd_millions",
]


def _target_common_panel(panel: pd.DataFrame) -> pd.DataFrame:
    return target_common_panel(panel)


def _diagnostic_signal(panel: pd.DataFrame) -> tuple[str, list[str]]:
    periods = panel["period"].nunique() if "period" in panel.columns else 0
    groups = panel["bank_group"].nunique() if "bank_group" in panel.columns else 0
    observed_groups = set(panel["bank_group"].dropna().astype(str)) if "bank_group" in panel.columns else set()
    target_groups = len(observed_groups.intersection(TARGET_H8_GROUPS))
    target_common = _target_common_panel(panel)
    target_common_periods = target_common["period"].nunique() if len(target_common) else 0
    context_complete = (
        float(target_common.get("is_context_complete", pd.Series(False, index=target_common.index)).mean())
        if len(target_common)
        else 0.0
    )
    bill_variation_frame = target_common if len(target_common) else panel
    bill_variation = (
        bill_variation_frame.get(
            "bill_heavy_month", pd.Series(False, index=bill_variation_frame.index)
        ).nunique()
        > 1
        or bill_variation_frame.get(
            "coupon_heavy_month", pd.Series(False, index=bill_variation_frame.index)
        ).nunique()
        > 1
    )
    coupon_rows = int(
        bill_variation_frame.get(
            "coupon_heavy_month", pd.Series(False, index=bill_variation_frame.index)
        )
        .fillna(False)
        .astype(bool)
        .sum()
    )
    high_bill_rows = int(
        bill_variation_frame.get(
            "high_bill_share_month", pd.Series(False, index=bill_variation_frame.index)
        )
        .fillna(False)
        .astype(bool)
        .sum()
    )
    low_bill_rows = int(
        bill_variation_frame.get(
            "low_bill_share_month", pd.Series(False, index=bill_variation_frame.index)
        )
        .fillna(False)
        .astype(bool)
        .sum()
    )

    reasons = [
        f"sample periods: {periods}",
        f"bank groups observed: {groups}",
        f"target H.8 groups observed: {target_groups} of {len(TARGET_H8_GROUPS)}",
        f"common target-group periods: {target_common_periods}",
        f"common-sample context-complete row share: {context_complete:.2f}",
        f"fixed-threshold bill/coupon variation present: {bill_variation}",
        f"fixed-threshold coupon-heavy rows: {coupon_rows}",
        f"relative high-bill rows: {high_bill_rows}",
        f"relative low-bill rows: {low_bill_rows}",
    ]
    if target_groups == 0:
        reasons.append("current H.8 reuse is aggregate-only; large/small/foreign split is still missing")
        return "NO-GO for heavy bank-level ingestion until target H.8 group coverage is available", reasons
    if target_common_periods >= 24 and target_groups >= 3 and context_complete >= 0.75 and bill_variation:
        return "PROVISIONAL GO for a scoped bank-level design memo", reasons
    if target_common_periods >= 12 and target_groups >= 2 and bill_variation:
        return "PARTIAL GO: improve coverage before Call Report or FR Y-9C ingestion", reasons
    return "NO-GO for heavy bank-level ingestion until H.8 coverage/context improves", reasons


def _common_sample_row(sample_summary: pd.DataFrame) -> pd.Series | None:
    if sample_summary.empty:
        return None
    required = {"sample", "bank_group"}
    if not required.issubset(sample_summary.columns):
        return None
    common = sample_summary.loc[
        (sample_summary["sample"] == "common_target_periods")
        & (sample_summary["bank_group"] == "all_target_groups")
    ]
    if common.empty:
        return None
    return common.iloc[0]


def _coupon_rows_from_summary(panel: pd.DataFrame, sample_summary: pd.DataFrame) -> int:
    row = _common_sample_row(sample_summary)
    if row is not None:
        return int(row.get("coupon_heavy_rows", 0))
    common = _target_common_panel(panel)
    return int(
        common.get("coupon_heavy_month", pd.Series(False, index=common.index))
        .fillna(False)
        .astype(bool)
        .sum()
    )


def _context_share_from_summary(panel: pd.DataFrame, sample_summary: pd.DataFrame) -> float:
    row = _common_sample_row(sample_summary)
    if row is not None:
        return float(row.get("context_complete_share", 0.0))
    common = _target_common_panel(panel)
    if common.empty:
        return 0.0
    return float(common.get("is_context_complete", pd.Series(False, index=common.index)).mean())


def _relative_stability_counts(relative_contrasts: pd.DataFrame) -> tuple[int, int, bool]:
    if relative_contrasts.empty:
        return 0, 0, False
    required = {"sample", "outcome_change", "same_sign_as_other_sample"}
    if not required.issubset(relative_contrasts.columns):
        return 0, 0, False
    common = relative_contrasts.loc[
        relative_contrasts["sample"].eq("common_target_periods")
        & relative_contrasts["outcome_change"].isin(LEVEL_OUTCOME_COLUMNS)
    ]
    if common.empty:
        return 0, 0, False
    stable = int(common["same_sign_as_other_sample"].fillna(False).astype(bool).sum())
    total = int(len(common))
    loan_rows = common.loc[common["outcome_change"].eq("d_loans_usd_millions")]
    loans_stable = bool(len(loan_rows) and loan_rows["same_sign_as_other_sample"].fillna(False).astype(bool).all())
    return stable, total, loans_stable


def _mechanism_recommendation(
    panel: pd.DataFrame,
    sample_summary: pd.DataFrame,
    relative_contrasts: pd.DataFrame,
) -> tuple[str, list[str]]:
    recommendation, reasons = _diagnostic_signal(panel)
    observed_groups = set(panel["bank_group"].dropna().astype(str)) if "bank_group" in panel.columns else set()
    target_groups = len(observed_groups.intersection(TARGET_H8_GROUPS))
    if target_groups == 0:
        return recommendation, reasons

    coupon_rows = _coupon_rows_from_summary(panel, sample_summary)
    context_share = _context_share_from_summary(panel, sample_summary)
    stable, total, loans_stable = _relative_stability_counts(relative_contrasts)
    if total:
        reasons.extend(
            [
                f"relative level contrasts stable across samples: {stable} of {total}",
                f"relative loan-growth signs stable across target groups: {loans_stable}",
            ]
        )

    if coupon_rows < 12:
        return (
            "PARTIAL GO: H.8 mechanism context only; fixed bill/coupon support is insufficient",
            reasons,
        )
    if total and stable < total:
        return (
            "PARTIAL GO: H.8 mechanism context only; relative-bucket stability is mixed",
            reasons,
        )
    if context_share < 0.75:
        return (
            "PARTIAL GO: improve context coverage before Call Report or FR Y-9C ingestion",
            reasons,
        )
    return recommendation, reasons


def write_go_no_go_report(
    *,
    panel_path: str | Path,
    output_path: str | Path,
    diagnostics_dir: str | Path | None = None,
) -> Path:
    """Write a concise markdown go/no-go report for review."""

    panel = read_csv(panel_path)
    sample_summary = pd.DataFrame()
    relative_contrasts = pd.DataFrame()
    if diagnostics_dir is not None:
        diag = Path(diagnostics_dir)
        if (diag / "sample_summary.csv").exists():
            sample_summary = read_csv(diag / "sample_summary.csv")
        if (diag / "relative_bill_share_contrasts.csv").exists():
            relative_contrasts = read_csv(diag / "relative_bill_share_contrasts.csv")
    recommendation, reasons = _mechanism_recommendation(panel, sample_summary, relative_contrasts)
    out = ensure_parent(output_path)

    diagnostics_note = ""
    if diagnostics_dir is not None:
        diag = Path(diagnostics_dir)
        available = sorted(path.name for path in diag.glob("*.csv")) if diag.exists() else []
        diagnostics_note = "\n## Diagnostic tables reviewed\n\n" + "\n".join(
            f"- `{name}`" for name in available
        )
        if not available:
            diagnostics_note += "- No diagnostic tables found.\n"
        else:
            diagnostics_note += "\n"

    stable, total, loans_stable = _relative_stability_counts(relative_contrasts)
    stability_lines = [
        f"- fixed-threshold coupon-heavy rows in common target-group sample: {_coupon_rows_from_summary(panel, sample_summary)}",
        f"- common-sample context-complete row share: {_context_share_from_summary(panel, sample_summary):.2f}",
    ]
    if total:
        stability_lines.extend(
            [
                f"- relative high-minus-low level contrasts stable across samples: {stable} of {total}",
                f"- relative loan-growth signs stable across target groups: {loans_stable}",
            ]
        )
    else:
        stability_lines.append("- relative high-minus-low stability was not available.")

    group_rows = []
    for group, gdf in panel.groupby("bank_group"):
        group_rows.append(
            f"- `{group}`: {len(gdf)} rows, {gdf['period'].min()} to {gdf['period'].max()}"
        )

    report = f"""# bankcap H.8 Go/No-Go Report

## Recommendation

**{recommendation}.**

## Gate checks

{chr(10).join(f"- {reason}" for reason in reasons)}

## Stability screen

{chr(10).join(stability_lines)}

## Bank-group coverage

{chr(10).join(group_rows) if group_rows else "- No bank-group rows found."}

## Interpretation

A GO result means only that the low-cost H.8 mechanism screen has enough variation and coverage to
justify drafting a bank-level design memo. It does not mean that bank-level data engineering should
begin without an explicit MDRM-code map, identifier strategy, merger/survivorship plan, and
pre-trend specification.
{diagnostics_note}
{CLAIM_BOUNDARY_TEXT}
## Next implementation branch

1. Treat fixed bill/coupon contrasts as unsupported unless coupon-heavy support improves.
2. Use relative high-bill and low-bill buckets as the current descriptive mechanism screen.
3. Keep Call Report / FR Y-9C ingestion blocked unless a separate design memo explains why the
   mixed stability pattern is still worth the bank-level data cost.
"""
    out.write_text(report, encoding="utf-8")
    return out


def _fmt_number(value: object, digits: int = 2) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "NA"
    if pd.isna(numeric):
        return "NA"
    return f"{numeric:.{digits}f}"


def _response_lines(response: pd.DataFrame, *, max_rows: int | None = None) -> list[str]:
    if response.empty:
        return ["- No response table is available."]
    lines = []
    bucket_col = "treasury_context_bucket"
    if bucket_col not in response.columns and "relative_bill_share_bucket" in response.columns:
        bucket_col = "relative_bill_share_bucket"
    ordered = response.sort_values(["bank_group", bucket_col])
    if max_rows is not None:
        ordered = ordered.head(max_rows)
    for _, row in ordered.iterrows():
        lines.append(
            "- "
            f"`{row['bank_group']}` / `{row[bucket_col]}`: "
            f"n={int(row['n_rows'])}, "
            f"d_securities={_fmt_number(row.get('d_securities_usd_millions'), 1)}, "
            f"d_deposits={_fmt_number(row.get('d_deposits_usd_millions'), 1)}, "
            f"d_loans={_fmt_number(row.get('d_loans_usd_millions'), 1)}, "
            f"d_cash={_fmt_number(row.get('d_cash_assets_usd_millions'), 1)}"
        )
    return lines


def _sample_warning(sample_summary: pd.DataFrame) -> str:
    if sample_summary.empty:
        return "No sample summary was available; do not interpret response differences."
    common = sample_summary.loc[
        (sample_summary["sample"] == "common_target_periods")
        & (sample_summary["bank_group"] == "all_target_groups")
    ]
    if common.empty:
        return "No common target-group sample is available; do not interpret response differences."
    row = common.iloc[0]
    coupon_rows = int(row.get("coupon_heavy_rows", 0))
    context_share = float(row.get("context_complete_share", 0.0))
    warnings = []
    if coupon_rows < 12:
        warnings.append(
            f"Coupon-heavy support is too thin in the common target-group sample "
            f"({coupon_rows} rows), so bill-versus-coupon contrasts are not stable."
        )
    if context_share < 0.75:
        warnings.append(
            f"Context completeness is {context_share:.2f}, below the full-go threshold; "
            "TGA-complete diagnostics should be read as a later-sample screen."
        )
    if not warnings:
        warnings.append("Common target-group coverage is adequate for a scoped mechanism memo.")
    return " ".join(warnings)


def _relative_stability_read(relative_contrasts: pd.DataFrame) -> str:
    if relative_contrasts.empty:
        return "Relative high-bill and low-bill stability could not be evaluated."
    common = relative_contrasts.loc[relative_contrasts["sample"].eq("common_target_periods")]
    if common.empty:
        return "Relative high-bill and low-bill stability could not be evaluated in the common sample."
    level_outcomes = common.loc[
        common["outcome_change"].isin(
            [
                "d_securities_usd_millions",
                "d_deposits_usd_millions",
                "d_loans_usd_millions",
                "d_cash_assets_usd_millions",
            ]
        )
    ]
    stable = int(level_outcomes["same_sign_as_other_sample"].sum())
    total = int(len(level_outcomes))
    loan_rows = level_outcomes.loc[level_outcomes["outcome_change"].eq("d_loans_usd_millions")]
    loans_stable = bool(len(loan_rows) and loan_rows["same_sign_as_other_sample"].all())
    if stable == total and total:
        return "Relative high-bill versus low-bill signs are stable across common and TGA-complete samples."
    if loans_stable:
        return (
            f"Relative high-bill versus low-bill signs are mixed ({stable} of {total} level contrasts "
            "match across samples), though loan-growth signs are stable for all target groups."
        )
    return (
        f"Relative high-bill versus low-bill signs are mixed ({stable} of {total} level contrasts "
        "match across samples)."
    )


def _cutoff_sensitivity_lines(sensitivity: pd.DataFrame) -> list[str]:
    if sensitivity.empty:
        return ["- No relative cutoff sensitivity table is available."]
    lines = []
    for _, row in sensitivity.sort_values(["low_quantile", "high_quantile"]).iterrows():
        lines.append(
            "- "
            f"q{_fmt_number(row.get('low_quantile'), 2)}/q{_fmt_number(row.get('high_quantile'), 2)}: "
            f"common high/low rows={int(row.get('common_high_rows', 0))}/"
            f"{int(row.get('common_low_rows', 0))}, "
            f"stable level contrasts={int(row.get('stable_level_contrasts', 0))}/"
            f"{int(row.get('total_level_contrasts', 0))}, "
            f"loan signs stable={bool(row.get('loan_growth_signs_stable', False))}"
        )
    return lines


def _safe_int(value: object) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _event_window_lines(contrasts: pd.DataFrame, *, max_rows_per_event: int = 3) -> list[str]:
    if contrasts.empty:
        return ["- No event-window contrast table is available."]
    required = {"event_flag", "bank_group", "contrast", "outcome_change", "difference", "n_events"}
    if not required.issubset(contrasts.columns):
        return ["- Event-window contrast table is missing required columns."]
    level = contrasts.loc[
        contrasts["outcome_change"].isin(
            [
                "d_securities_usd_millions",
                "d_deposits_usd_millions",
                "d_loans_usd_millions",
                "d_cash_assets_usd_millions",
            ]
        )
    ].copy()
    if level.empty:
        return ["- No level-change event-window contrasts are available."]
    level["abs_difference"] = pd.to_numeric(level["difference"], errors="coerce").abs()
    lines = []
    for event_flag, event_rows in level.sort_values("event_flag").groupby("event_flag"):
        ordered = event_rows.sort_values("abs_difference", ascending=False).head(max_rows_per_event)
        for _, row in ordered.iterrows():
            lines.append(
                "- "
                f"`{event_flag}` / `{row['bank_group']}` / `{row['contrast']}` "
                f"`{row['outcome_change']}`: difference={_fmt_number(row['difference'], 1)}, "
                f"events={int(row.get('n_events', 0))}"
            )
    return lines


def write_mechanism_summary_json(
    *,
    panel_path: str | Path,
    diagnostics_dir: str | Path,
    output_path: str | Path,
) -> Path:
    """Write a compact machine-readable summary of the H.8 mechanism package."""

    panel = read_csv(panel_path)
    diag = Path(diagnostics_dir)
    sample_summary = read_csv(diag / "sample_summary.csv") if (diag / "sample_summary.csv").exists() else pd.DataFrame()
    relative_contrasts = (
        read_csv(diag / "relative_bill_share_contrasts.csv")
        if (diag / "relative_bill_share_contrasts.csv").exists()
        else pd.DataFrame()
    )
    cutoff_sensitivity = (
        read_csv(diag / "relative_bill_share_cutoff_sensitivity.csv")
        if (diag / "relative_bill_share_cutoff_sensitivity.csv").exists()
        else pd.DataFrame()
    )
    event_summary = (
        read_csv(diag / "event_window_summary.csv")
        if (diag / "event_window_summary.csv").exists()
        else pd.DataFrame()
    )

    recommendation, reasons = _mechanism_recommendation(panel, sample_summary, relative_contrasts)
    common = _target_common_panel(panel)
    stable, total, loans_stable = _relative_stability_counts(relative_contrasts)
    common_row = _common_sample_row(sample_summary)
    if common_row is not None:
        common_periods = _safe_int(common_row.get("n_periods"))
        first_period = str(common_row.get("first_period", ""))
        last_period = str(common_row.get("last_period", ""))
    else:
        common_periods = int(common["period"].nunique()) if len(common) else 0
        first_period = str(common["period"].min()) if len(common) else ""
        last_period = str(common["period"].max()) if len(common) else ""
    common_summary = {
        "rows": _safe_int(common_row.get("n_rows")) if common_row is not None else len(common),
        "periods": common_periods,
        "first_period": first_period,
        "last_period": last_period,
        "context_complete_share": _context_share_from_summary(panel, sample_summary),
        "coupon_heavy_rows": _coupon_rows_from_summary(panel, sample_summary),
        "high_bill_share_rows": _safe_int(common_row.get("high_bill_share_rows")) if common_row is not None else 0,
        "low_bill_share_rows": _safe_int(common_row.get("low_bill_share_rows")) if common_row is not None else 0,
    }

    coverage = []
    for group, gdf in panel.sort_values(["bank_group", "period"]).groupby("bank_group"):
        coverage.append(
            {
                "bank_group": group,
                "rows": int(len(gdf)),
                "first_period": str(gdf["period"].min()),
                "last_period": str(gdf["period"].max()),
            }
        )

    cutoff_rows = []
    cutoff_source = (
        cutoff_sensitivity.sort_values(["low_quantile", "high_quantile"]).iterrows()
        if not cutoff_sensitivity.empty
        else []
    )
    for _, row in cutoff_source:
        cutoff_rows.append(
            {
                "low_quantile": _safe_float(row.get("low_quantile")),
                "high_quantile": _safe_float(row.get("high_quantile")),
                "common_high_rows": _safe_int(row.get("common_high_rows")),
                "common_low_rows": _safe_int(row.get("common_low_rows")),
                "stable_level_contrasts": _safe_int(row.get("stable_level_contrasts")),
                "total_level_contrasts": _safe_int(row.get("total_level_contrasts")),
                "loan_growth_signs_stable": bool(row.get("loan_growth_signs_stable", False)),
            }
        )

    event_rows = []
    if not event_summary.empty:
        for event_flag, gdf in event_summary.groupby("event_flag"):
            event_rows.append(
                {
                    "event_flag": event_flag,
                    "bank_groups": sorted(gdf["bank_group"].dropna().astype(str).unique().tolist()),
                    "n_events": int(gdf["n_events"].max()) if "n_events" in gdf else 0,
                    "first_event_start_period": str(gdf["first_event_start_period"].min())
                    if "first_event_start_period" in gdf
                    else "",
                    "last_event_start_period": str(gdf["last_event_start_period"].max())
                    if "last_event_start_period" in gdf
                    else "",
                }
            )

    summary = {
        "package": "bankcap_h8_mechanism_screen",
        "recommendation": recommendation,
        "claim_boundary": "H.8 bank-group evidence is mechanism context, not bank-level identification or causal absorption evidence.",
        "gate_checks": reasons,
        "common_target_sample": common_summary,
        "bank_group_coverage": coverage,
        "relative_stability": {
            "stable_level_contrasts": stable,
            "total_level_contrasts": total,
            "loan_growth_signs_stable": loans_stable,
            "read": _relative_stability_read(relative_contrasts),
        },
        "relative_cutoff_sensitivity": cutoff_rows,
        "event_window_inventory": event_rows,
        "bank_level_ingestion": {
            "status": "blocked",
            "reason": "Requires a separate design memo because H.8 stability remains mixed.",
        },
    }

    out = ensure_parent(output_path)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def write_mechanism_memo(
    *,
    panel_path: str | Path,
    diagnostics_dir: str | Path,
    output_path: str | Path,
) -> Path:
    """Write a guarded H.8 mechanism-screen memo from generated diagnostics."""

    panel = read_csv(panel_path)
    diag = Path(diagnostics_dir)
    sample_summary = read_csv(diag / "sample_summary.csv") if (diag / "sample_summary.csv").exists() else pd.DataFrame()
    response = (
        read_csv(diag / "bank_group_response_table.csv")
        if (diag / "bank_group_response_table.csv").exists()
        else pd.DataFrame()
    )
    common_response = (
        read_csv(diag / "common_target_response_table.csv")
        if (diag / "common_target_response_table.csv").exists()
        else pd.DataFrame()
    )
    tga_response = (
        read_csv(diag / "tga_complete_response_table.csv")
        if (diag / "tga_complete_response_table.csv").exists()
        else pd.DataFrame()
    )
    common_relative_response = (
        read_csv(diag / "common_target_relative_bill_share_response_table.csv")
        if (diag / "common_target_relative_bill_share_response_table.csv").exists()
        else pd.DataFrame()
    )
    tga_relative_response = (
        read_csv(diag / "tga_complete_relative_bill_share_response_table.csv")
        if (diag / "tga_complete_relative_bill_share_response_table.csv").exists()
        else pd.DataFrame()
    )
    relative_contrasts = (
        read_csv(diag / "relative_bill_share_contrasts.csv")
        if (diag / "relative_bill_share_contrasts.csv").exists()
        else pd.DataFrame()
    )
    cutoff_sensitivity = (
        read_csv(diag / "relative_bill_share_cutoff_sensitivity.csv")
        if (diag / "relative_bill_share_cutoff_sensitivity.csv").exists()
        else pd.DataFrame()
    )
    trends = read_csv(diag / "bank_group_trends.csv") if (diag / "bank_group_trends.csv").exists() else pd.DataFrame()
    guarded = (
        read_csv(diag / "guarded_regressions.csv")
        if (diag / "guarded_regressions.csv").exists()
        else pd.DataFrame()
    )
    event_contrasts = (
        read_csv(diag / "event_window_contrasts.csv")
        if (diag / "event_window_contrasts.csv").exists()
        else pd.DataFrame()
    )
    recommendation, reasons = _mechanism_recommendation(panel, sample_summary, relative_contrasts)
    out = ensure_parent(output_path)

    common = _target_common_panel(panel)
    tga_complete = tga_complete_target_panel(panel)
    common_period_text = "none"
    if len(common):
        common_period_text = f"{common['period'].min()} to {common['period'].max()}"
    tga_period_text = "none"
    if len(tga_complete):
        tga_period_text = f"{tga_complete['period'].min()} to {tga_complete['period'].max()}"

    trend_lines = []
    for _, row in trends.sort_values("bank_group").iterrows() if not trends.empty else []:
        trend_lines.append(
            "- "
            f"`{row['bank_group']}`: {int(row['n_rows'])} rows, "
            f"{row['first_period']} to {row['last_period']}; "
            f"last securities/deposits={_fmt_number(row.get('last_securities_deposits_ratio'), 3)}, "
            f"last cash/deposits={_fmt_number(row.get('last_cash_deposits_ratio'), 3)}, "
            f"last loans/deposits={_fmt_number(row.get('last_loans_deposits_ratio'), 3)}"
        )

    strongest = pd.DataFrame()
    if not guarded.empty and "r_squared" in guarded.columns:
        strongest = guarded.sort_values("r_squared", ascending=False).head(6)
    guarded_lines = []
    for _, row in strongest.iterrows():
        guarded_lines.append(
            "- "
            f"`{row['bank_group']}` `{row['outcome_change']}`: "
            f"bill-share coefficient={_fmt_number(row.get('bill_share_coef'), 3)}, "
            f"R2={_fmt_number(row.get('r_squared'), 4)}, n={int(row.get('n_obs', 0))}"
        )
    if not guarded_lines:
        guarded_lines = ["- No guarded regression table is available."]

    contrast_lines = []
    if not relative_contrasts.empty:
        common_contrasts = relative_contrasts.loc[
            relative_contrasts["sample"].eq("common_target_periods")
            & relative_contrasts["outcome_change"].isin(
                [
                    "d_securities_usd_millions",
                    "d_deposits_usd_millions",
                    "d_loans_usd_millions",
                    "d_cash_assets_usd_millions",
                ]
            )
        ]
        for _, row in common_contrasts.sort_values(["bank_group", "outcome_change"]).iterrows():
            stable = "same sign in TGA-complete sample" if row["same_sign_as_other_sample"] else "sign changes in TGA-complete sample"
            contrast_lines.append(
                "- "
                f"`{row['bank_group']}` `{row['outcome_change']}`: "
                f"high-minus-low={_fmt_number(row['high_minus_low'], 1)}; {stable}"
            )
    if not contrast_lines:
        contrast_lines = ["- No relative contrast table is available."]

    memo = f"""# H.8 Mechanism-Screen Memo

## Bottom line

{recommendation}. {_sample_warning(sample_summary)} {_relative_stability_read(relative_contrasts)}

## Gate checks

{chr(10).join(f"- {reason}" for reason in reasons)}
- common target-group sample: {common_period_text}

## Balance-sheet coverage

{chr(10).join(trend_lines) if trend_lines else "- No trend table is available."}

## Bill-heavy and coupon-heavy response support

Full target-group rows:

{chr(10).join(_response_lines(response))}

Common target-group sample:

{chr(10).join(_response_lines(common_response))}

TGA-complete common target-group sample ({tga_period_text}):

{chr(10).join(_response_lines(tga_response))}

## Relative high-bill and low-bill response support

These buckets compare the top and bottom configured bill-share quantiles. They are relative issuance
composition screens, not pure bill-versus-coupon regimes.

Common target-group sample:

{chr(10).join(_response_lines(common_relative_response))}

TGA-complete common target-group sample ({tga_period_text}):

{chr(10).join(_response_lines(tga_relative_response))}

High-minus-low stability checks:

{chr(10).join(contrast_lines)}

Relative cutoff sensitivity:

{chr(10).join(_cutoff_sensitivity_lines(cutoff_sensitivity))}

## Guarded bill-share screens

{chr(10).join(guarded_lines)}

## Event-window screens

These are descriptive calendar-window contrasts around configured policy/stress windows. They are
not causal event-study estimates and do not identify bank-level exposure.

{chr(10).join(_event_window_lines(event_contrasts))}

## Interpretation boundary

This memo is descriptive mechanism screening. It does not identify individual-bank absorption,
bank-level duration exposure, causal Treasury absorption, or merger-adjusted bank behavior. The H.8
securities measure is Treasury-and-agency securities. A bank-level memo should come before any Call
Report or FR Y-9C ingestion.

## Recommended next branch

1. Treat fixed-threshold coupon-heavy contrasts as unsupported under the current data.
2. Use relative high-bill and low-bill buckets as the defensible first-pass composition comparison.
3. Inspect the TGA-complete rows as a later-sample mechanism check, not a full historical result.
4. Keep `bankcap` as an H.8 mechanism-context project for now; do not start Call Report or FR Y-9C
   ingestion until a separate design memo explains why the mixed stability pattern is still worth the
   bank-level data cost.
"""
    out.write_text(memo, encoding="utf-8")
    return out

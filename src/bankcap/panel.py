"""Merge H.8 outcomes with Treasury financing context."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bankcap.io import read_csv, write_csv

CONTEXT_REQUIRED_FOR_COMPLETENESS = [
    "bill_share",
    "wam_months",
    "gross_issuance_usd",
    "liquidity_weighted_treasury_supply_usd",
    "tga_change_usd_millions",
]


def build_analysis_panel(
    h8_path: str | Path,
    context_path: str | Path,
    output_path: str | Path | None = None,
    *,
    how: str = "left",
) -> pd.DataFrame:
    """Merge an H.8 bank-group outcome panel to a Treasury context panel on ``period``."""

    h8 = read_csv(h8_path)
    context = read_csv(context_path)
    if "period" not in h8.columns or "period" not in context.columns:
        raise ValueError("Both H.8 and Treasury context panels must contain a 'period' column")

    # Avoid duplicate date/frequency columns from context; H.8 defines the observation unit.
    context_keep = [c for c in context.columns if c not in {"date", "frequency"}]
    panel = h8.merge(context[context_keep], on="period", how=how, validate="many_to_one")

    for column in [
        "qt_qe_regime",
        "high_rate_regime",
        "bill_heavy_month",
        "coupon_heavy_month",
        "slr_relief_window",
        "rate_duration_shock_window",
        "banking_stress_2023_window",
        "large_tga_rebuild_window",
    ]:
        if column not in panel.columns:
            panel[column] = False if column != "qt_qe_regime" else "unknown"

    existing = [c for c in CONTEXT_REQUIRED_FOR_COMPLETENESS if c in panel.columns]
    if existing:
        panel["is_context_complete"] = panel[existing].notna().all(axis=1)
    else:
        panel["is_context_complete"] = False

    bool_cols = [c for c in panel.columns if c.endswith("_window") or c.endswith("_month")]
    bool_cols.append("high_rate_regime")
    for column in sorted(set(bool_cols)):
        if column in panel.columns:
            panel[column] = panel[column].fillna(False).astype(bool)

    panel = panel.sort_values(["period", "bank_group"]).reset_index(drop=True)
    if output_path is not None:
        write_csv(panel, output_path)
    return panel

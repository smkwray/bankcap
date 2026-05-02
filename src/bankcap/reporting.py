"""Go/no-go reporting for the H.8 bank-group screen."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bankcap.io import ensure_parent, read_csv

CLAIM_BOUNDARY_TEXT = """\
## Claim boundary

This report is a mechanism screen, not bank-level identification. H.8 bank-group data cannot support
claims about individual-bank heterogeneity, merger-adjusted bank behavior, bank-level duration
exposure, or causal absorption. H.8 securities should be labeled as an aggregate that may combine
Treasury and agency securities unless a source-specific mapping proves otherwise.
"""


def _diagnostic_signal(panel: pd.DataFrame) -> tuple[str, list[str]]:
    periods = panel["period"].nunique() if "period" in panel.columns else 0
    groups = panel["bank_group"].nunique() if "bank_group" in panel.columns else 0
    context_complete = (
        float(panel.get("is_context_complete", pd.Series(False, index=panel.index)).mean())
        if len(panel)
        else 0.0
    )
    bill_variation = (
        panel.get("bill_heavy_month", pd.Series(False, index=panel.index)).nunique() > 1
        or panel.get("coupon_heavy_month", pd.Series(False, index=panel.index)).nunique() > 1
    )

    reasons = [
        f"sample periods: {periods}",
        f"bank groups observed: {groups}",
        f"context-complete row share: {context_complete:.2f}",
        f"bill/coupon context variation present: {bill_variation}",
    ]
    if periods >= 24 and groups >= 3 and context_complete >= 0.75 and bill_variation:
        return "PROVISIONAL GO for a scoped bank-level design memo", reasons
    if periods >= 12 and groups >= 2 and bill_variation:
        return "PARTIAL GO: improve coverage before Call Report or FR Y-9C ingestion", reasons
    return "NO-GO for heavy bank-level ingestion until H.8 coverage/context improves", reasons


def write_go_no_go_report(
    *,
    panel_path: str | Path,
    output_path: str | Path,
    diagnostics_dir: str | Path | None = None,
) -> Path:
    """Write a concise markdown go/no-go report for review."""

    panel = read_csv(panel_path)
    recommendation, reasons = _diagnostic_signal(panel)
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

1. Inspect bill-heavy versus coupon-heavy response tables by bank group.
2. Check whether securities/deposits, cash/deposits, and loans/deposits move differently across
   large domestic, small domestic, and foreign-related groups.
3. Draft a Call Report / FR Y-9C data-cost memo only if the screen shows stable, interpretable
   variation that is not solely a calendar-regime artifact.
"""
    out.write_text(report, encoding="utf-8")
    return out

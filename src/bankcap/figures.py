"""Lightweight SVG figures for the H.8 mechanism screen."""

from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd

from bankcap.io import ensure_parent, read_csv

GROUP_LABELS = {
    "foreign_related_institutions": "Foreign-related",
    "large_domestic_banks": "Large domestic",
    "small_domestic_banks": "Small domestic",
}

GROUP_COLORS = {
    "foreign_related_institutions": "#4B6B8A",
    "large_domestic_banks": "#7B4F71",
    "small_domestic_banks": "#5D7A46",
}

OUTCOME_LABELS = {
    "d_securities_usd_millions": "Securities",
    "d_deposits_usd_millions": "Deposits",
    "d_loans_usd_millions": "Loans",
    "d_cash_assets_usd_millions": "Cash assets",
}


def _svg_text(x: float, y: float, text: object, *, size: int = 12, weight: str = "400") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="#1f2933">{escape(str(text))}</text>'
    )


def _scale(value: float, domain: tuple[float, float], range_: tuple[float, float]) -> float:
    lo, hi = domain
    start, end = range_
    if hi == lo:
        return (start + end) / 2
    return start + (value - lo) / (hi - lo) * (end - start)


def _svg_frame(width: int, height: int, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        '<rect width="100%" height="100%" fill="#ffffff"/>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def _write_svg(path: str | Path, content: str) -> Path:
    out = ensure_parent(path)
    out.write_text(content, encoding="utf-8")
    return out


def write_ratio_trends_svg(
    panel_path: str | Path,
    output_path: str | Path,
    *,
    start_period: str = "2003-01",
) -> Path:
    """Write a compact SVG line chart for H.8 balance-sheet ratios."""

    panel = read_csv(panel_path)
    panel = panel.loc[
        panel["bank_group"].isin(GROUP_LABELS)
        & panel["period"].astype(str).ge(start_period)
    ].copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    metrics = [
        ("securities_deposits_ratio", "Securities / deposits"),
        ("cash_deposits_ratio", "Cash / deposits"),
        ("loans_deposits_ratio", "Loans / deposits"),
    ]

    width, height = 980, 660
    left, right = 74, 28
    top, panel_h, gap = 86, 142, 44
    x_domain = (panel["date"].min().toordinal(), panel["date"].max().toordinal())
    body: list[str] = [
        _svg_text(34, 32, "H.8 balance-sheet ratios by bank group", size=18, weight="700"),
        _svg_text(34, 52, f"Monthly, {start_period} onward; descriptive mechanism context", size=12),
    ]

    plot_w = width - left - right
    for idx, (metric, title) in enumerate(metrics):
        y_top = top + idx * (panel_h + gap)
        y_bottom = y_top + panel_h
        values = pd.to_numeric(panel[metric], errors="coerce").dropna()
        y_domain = (float(values.min()), float(values.max()))
        body.append(_svg_text(34, y_top - 10, title, size=14, weight="700"))
        body.append(
            f'<line x1="{left}" y1="{y_bottom:.1f}" x2="{width - right}" y2="{y_bottom:.1f}" '
            'stroke="#d7dee8" stroke-width="1"/>'
        )
        body.append(
            f'<line x1="{left}" y1="{y_top:.1f}" x2="{left}" y2="{y_bottom:.1f}" '
            'stroke="#d7dee8" stroke-width="1"/>'
        )
        body.append(_svg_text(18, y_top + 4, f"{y_domain[1]:.2f}", size=10))
        body.append(_svg_text(18, y_bottom, f"{y_domain[0]:.2f}", size=10))
        for group, gdf in panel.sort_values("date").groupby("bank_group"):
            points = []
            for row in gdf.itertuples(index=False):
                value = getattr(row, metric)
                if pd.isna(value) or pd.isna(row.date):
                    continue
                x = _scale(row.date.toordinal(), x_domain, (left, left + plot_w))
                y = _scale(float(value), y_domain, (y_bottom, y_top))
                points.append(f"{x:.1f},{y:.1f}")
            if len(points) >= 2:
                body.append(
                    f'<polyline points="{" ".join(points)}" fill="none" '
                    f'stroke="{GROUP_COLORS[group]}" stroke-width="2.2"/>'
                )
        if idx == 0:
            legend_x = width - 430
            for j, group in enumerate(GROUP_LABELS):
                x = legend_x + j * 138
                body.append(
                    f'<rect x="{x}" y="21" width="14" height="14" fill="{GROUP_COLORS[group]}"/>'
                )
                body.append(_svg_text(x + 20, 33, GROUP_LABELS[group], size=11))

    return _write_svg(output_path, _svg_frame(width, height, body))


def write_relative_contrasts_svg(
    contrasts_path: str | Path,
    output_path: str | Path,
    *,
    sample: str = "common_target_periods",
) -> Path:
    """Write a grouped bar SVG for high-minus-low relative bill-share contrasts."""

    contrasts = read_csv(contrasts_path)
    contrasts = contrasts.loc[
        contrasts["sample"].eq(sample)
        & contrasts["outcome_change"].isin(OUTCOME_LABELS)
    ].copy()
    width, height = 980, 520
    left, right, top, bottom = 250, 36, 64, 62
    plot_w = width - left - right
    row_h = 32
    contrasts["label"] = contrasts.apply(
        lambda row: f"{GROUP_LABELS[row['bank_group']]}: {OUTCOME_LABELS[row['outcome_change']]}",
        axis=1,
    )
    max_abs = float(contrasts["high_minus_low"].abs().max())
    x_domain = (-max_abs, max_abs)
    zero_x = _scale(0, x_domain, (left, left + plot_w))
    body: list[str] = [
        _svg_text(34, 32, "Relative high-bill minus low-bill monthly changes", size=18, weight="700"),
        _svg_text(34, 52, "Common target-group sample; USD millions; descriptive, not causal", size=12),
        f'<line x1="{zero_x:.1f}" y1="{top - 18}" x2="{zero_x:.1f}" y2="{height - bottom + 12}" '
        'stroke="#7b8794" stroke-width="1.2"/>',
    ]
    for idx, row in enumerate(contrasts.sort_values(["bank_group", "outcome_change"]).itertuples(index=False)):
        y = top + idx * row_h
        value = float(row.high_minus_low)
        x = _scale(value, x_domain, (left, left + plot_w))
        bar_x = min(x, zero_x)
        bar_w = abs(x - zero_x)
        color = GROUP_COLORS[row.bank_group]
        body.append(_svg_text(24, y + 17, row.label, size=11))
        body.append(
            f'<rect x="{bar_x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="20" '
            f'fill="{color}" opacity="0.86"/>'
        )
        body.append(_svg_text(x + (6 if value >= 0 else -64), y + 15, f"{value:,.0f}", size=10))
    body.append(_svg_text(left, height - 22, f"{-max_abs:,.0f}", size=10))
    body.append(_svg_text(zero_x - 4, height - 22, "0", size=10))
    body.append(_svg_text(width - right - 54, height - 22, f"{max_abs:,.0f}", size=10))
    return _write_svg(output_path, _svg_frame(width, height, body))


def write_mechanism_figures(
    *,
    panel_path: str | Path,
    diagnostics_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write the standard H.8 mechanism-screen SVG figure set."""

    out_dir = Path(output_dir)
    outputs = {
        "ratio_trends": out_dir / "h8_ratio_trends.svg",
        "relative_contrasts": out_dir / "relative_bill_share_contrasts.svg",
    }
    write_ratio_trends_svg(panel_path, outputs["ratio_trends"])
    write_relative_contrasts_svg(
        Path(diagnostics_dir) / "relative_bill_share_contrasts.csv",
        outputs["relative_contrasts"],
    )
    return outputs

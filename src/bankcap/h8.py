"""H.8 bank-group panel builder.

The seed implementation expects a standardized long-form H.8-style input. It also accepts common
aliases so imported ``liqsub`` or Federal Reserve exports can be used without rewriting the
panel logic.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bankcap.io import read_csv, write_csv

BANK_GROUPS = {
    "large_domestic_banks",
    "small_domestic_banks",
    "foreign_related_institutions",
}

GROUP_ALIASES = {
    "large domestically chartered banks": "large_domestic_banks",
    "large_domestically_chartered_banks": "large_domestic_banks",
    "large_domestic": "large_domestic_banks",
    "large": "large_domestic_banks",
    "small domestically chartered banks": "small_domestic_banks",
    "small_domestically_chartered_banks": "small_domestic_banks",
    "small_domestic": "small_domestic_banks",
    "small": "small_domestic_banks",
    "foreign-related institutions": "foreign_related_institutions",
    "foreign related institutions": "foreign_related_institutions",
    "foreign_related": "foreign_related_institutions",
    "foreign": "foreign_related_institutions",
}

H8_ALIASES = {
    "date": ["date", "observation_date", "week", "month", "period"],
    "bank_group": ["bank_group", "group", "h8_group", "bank_type"],
    "securities_usd_millions": [
        "securities_usd_millions",
        "securities",
        "bank_securities_usd_millions",
        "h8_securities_usd_millions",
        "treasury_agency_securities_usd_millions",
        "securities_treasury_agency_usd_millions",
    ],
    "deposits_usd_millions": [
        "deposits_usd_millions",
        "deposits",
        "bank_deposits_usd_millions",
        "h8_deposits_usd_millions",
    ],
    "loans_usd_millions": [
        "loans_usd_millions",
        "loans",
        "bank_loans_usd_millions",
        "h8_loans_usd_millions",
    ],
    "cash_assets_usd_millions": [
        "cash_assets_usd_millions",
        "cash_assets",
        "cash_usd_millions",
        "bank_cash_assets_usd_millions",
        "reserves_cash_assets_usd_millions",
    ],
}

LEVEL_COLUMNS = [
    "securities_usd_millions",
    "deposits_usd_millions",
    "loans_usd_millions",
    "cash_assets_usd_millions",
]

RATIO_COLUMNS = [
    "securities_deposits_ratio",
    "cash_deposits_ratio",
    "loans_deposits_ratio",
]

SECURITY_LABEL = (
    "H.8 securities aggregate; may combine Treasury and agency securities depending source mapping."
)


def _coalesce_column(df: pd.DataFrame, aliases: list[str], target: str) -> pd.Series:
    for alias in aliases:
        if alias in df.columns:
            return df[alias]
    raise ValueError(f"Could not find column for {target}; accepted aliases: {aliases}")


def _normalize_group(value: object) -> str:
    text = str(value).strip()
    normalized = text.lower().replace("/", " ").replace("_", " ").replace("-", " ")
    normalized = " ".join(normalized.split())
    alias_key = normalized.replace(" ", "_")
    if text in BANK_GROUPS:
        return text
    if normalized in GROUP_ALIASES:
        return GROUP_ALIASES[normalized]
    if alias_key in GROUP_ALIASES:
        return GROUP_ALIASES[alias_key]
    raise ValueError(f"Unknown H.8 bank group: {value!r}")


def standardize_h8_input(df: pd.DataFrame) -> pd.DataFrame:
    """Return a canonical H.8 long-form dataframe from alias-tolerant input."""

    out = pd.DataFrame()
    for target, aliases in H8_ALIASES.items():
        out[target] = _coalesce_column(df, aliases, target)

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    if out["date"].isna().any():
        raise ValueError("H.8 input contains unparseable dates")

    out["bank_group"] = out["bank_group"].map(_normalize_group)
    for column in LEVEL_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out[LEVEL_COLUMNS].isna().any().any():
        missing = out[LEVEL_COLUMNS].isna().sum().to_dict()
        raise ValueError(f"H.8 input contains non-numeric or missing level values: {missing}")
    return out


def _period_from_date(series: pd.Series, frequency: str) -> pd.Series:
    if frequency == "monthly":
        return series.dt.to_period("M").astype(str)
    if frequency == "weekly":
        return series.dt.strftime("%Y-%m-%d")
    raise ValueError("frequency must be 'weekly' or 'monthly'")


def aggregate_frequency(df: pd.DataFrame, *, frequency: str, monthly_method: str = "last") -> pd.DataFrame:
    """Aggregate standardized H.8 input to weekly or monthly analysis periods."""

    frequency = frequency.lower()
    df = df.sort_values(["bank_group", "date"]).copy()
    df["period"] = _period_from_date(df["date"], frequency)
    df["frequency"] = frequency

    if frequency == "weekly":
        return df.drop_duplicates(["bank_group", "period"], keep="last")

    if monthly_method not in {"last", "mean"}:
        raise ValueError("monthly_method must be 'last' or 'mean'")
    group_cols = ["bank_group", "period", "frequency"]
    if monthly_method == "last":
        return df.groupby(group_cols, as_index=False).tail(1).reset_index(drop=True)

    agg = df.groupby(group_cols, as_index=False).agg({**{c: "mean" for c in LEVEL_COLUMNS}, "date": "max"})
    return agg


def add_ratios_and_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Add ratio and within-bank-group change columns."""

    out = df.sort_values(["bank_group", "date"]).copy()
    deposits = out["deposits_usd_millions"].replace({0: pd.NA})
    out["securities_deposits_ratio"] = out["securities_usd_millions"] / deposits
    out["cash_deposits_ratio"] = out["cash_assets_usd_millions"] / deposits
    out["loans_deposits_ratio"] = out["loans_usd_millions"] / deposits

    for column in LEVEL_COLUMNS + RATIO_COLUMNS:
        out[f"d_{column}"] = out.groupby("bank_group")[column].diff()
    out["h8_security_label"] = SECURITY_LABEL
    return out


def build_h8_bank_group_panel(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    frequency: str = "monthly",
    monthly_method: str = "last",
) -> pd.DataFrame:
    """Build the first-pass H.8 bank-group outcome panel.

    Parameters
    ----------
    input_path:
        Long-form H.8-like CSV with bank group, date, securities, deposits, loans, and cash assets.
    output_path:
        Optional CSV destination.
    frequency:
        ``monthly`` for the default H.8 screen or ``weekly`` for weekly diagnostics.
    monthly_method:
        ``last`` uses the final weekly observation in each month; ``mean`` averages weekly levels.
    """

    raw = read_csv(input_path)
    standardized = standardize_h8_input(raw)
    panel = aggregate_frequency(standardized, frequency=frequency, monthly_method=monthly_method)
    panel = add_ratios_and_changes(panel)

    order = [
        "period",
        "date",
        "frequency",
        "bank_group",
        *LEVEL_COLUMNS,
        *RATIO_COLUMNS,
        *(f"d_{column}" for column in LEVEL_COLUMNS + RATIO_COLUMNS),
        "h8_security_label",
    ]
    panel = panel[order].sort_values(["period", "bank_group"]).reset_index(drop=True)
    if output_path is not None:
        write_csv(panel, output_path)
    return panel

"""Calendar-window episode helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from bankcap.config import load_yaml


def period_to_timestamp(period: object) -> pd.Timestamp:
    """Convert a monthly or weekly period value to a timestamp."""

    text = str(period)
    if len(text) == 7 and text[4] == "-":
        return pd.Period(text, freq="M").to_timestamp("M")
    return pd.to_datetime(text)


def load_episode_config(path: str | Path) -> dict[str, Any]:
    """Load the episode-window config."""

    return load_yaml(path)


def apply_calendar_windows(
    df: pd.DataFrame,
    windows: dict[str, dict[str, Any]],
    *,
    period_col: str = "period",
) -> pd.DataFrame:
    """Apply configured calendar-window flags to a dataframe."""

    out = df.copy()
    dates = out[period_col].map(period_to_timestamp)
    for window_name, spec in windows.items():
        target = spec.get("target_column", window_name)
        start = pd.to_datetime(spec["start"])
        end = pd.to_datetime(spec["end"])
        flag = (dates >= start) & (dates <= end)
        if target in out.columns:
            out[target] = out[target].fillna(False).astype(bool) | flag
        else:
            out[target] = flag
    return out

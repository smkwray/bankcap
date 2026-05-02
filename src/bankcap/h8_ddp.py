"""Federal Reserve H.8 Data Download Program helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from bankcap.io import ensure_parent, sha256_file, write_csv

DDP_BASE_URL = "https://www.federalreserve.gov/datadownload/Output.aspx"

TARGET_GROUP_PACKAGES = {
    "large_domestic_banks": {
        "series": "07e492957747d0532d7727e9151f95ea",
        "filename": "large_domestic_banks_monthly_sa.csv",
    },
    "small_domestic_banks": {
        "series": "42db87d72249bc43f83a3129b163abe0",
        "filename": "small_domestic_banks_monthly_sa.csv",
    },
    "foreign_related_institutions": {
        "series": "037d1febb7b35a21963eac1a1d8b55d5",
        "filename": "foreign_related_institutions_monthly_sa.csv",
    },
}

H8_DDP_LEVEL_CODES = {
    "securities_usd_millions": "B1003",
    "loans_usd_millions": "B1020",
    "cash_assets_usd_millions": "B1048",
    "deposits_usd_millions": "B1058",
}

SECURITY_LABEL = "H.8 Treasury and agency securities, seasonally adjusted."
REQUEST_HEADERS = {"User-Agent": "bankcap data refresh"}


@dataclass(frozen=True)
class H8Package:
    bank_group: str
    series: str
    filename: str

    @property
    def url(self) -> str:
        return (
            f"{DDP_BASE_URL}?rel=H8&series={self.series}&lastobs=&from=&to=&filetype=csv"
            "&label=include&layout=seriescolumn&type=package"
        )


def target_packages() -> list[H8Package]:
    """Return the target monthly seasonally adjusted H.8 group packages."""

    return [
        H8Package(bank_group=group, series=metadata["series"], filename=metadata["filename"])
        for group, metadata in TARGET_GROUP_PACKAGES.items()
    ]


def download_target_group_packages(
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Download target H.8 DDP CSV packages into an ignored local directory."""

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for package in target_packages():
        dest = out_dir / package.filename
        downloaded = False
        if overwrite or not dest.exists():
            ensure_parent(dest)
            request = Request(package.url, headers=REQUEST_HEADERS)
            with urlopen(request) as response, dest.open("wb") as handle:
                handle.write(response.read())
            downloaded = True
        rows.append(
            {
                "bank_group": package.bank_group,
                "series_package": package.series,
                "url": package.url,
                "local_path": str(dest),
                "downloaded": downloaded,
                "sha256": sha256_file(dest),
            }
        )
    return pd.DataFrame(rows)


def _find_ddp_column(columns: list[str], code_prefix: str) -> str:
    matches = [column for column in columns if column.startswith(code_prefix)]
    if len(matches) != 1:
        raise ValueError(f"Expected one DDP column starting {code_prefix}; found {matches}")
    return matches[0]


def normalize_h8_ddp_package(path: str | Path, bank_group: str) -> pd.DataFrame:
    """Normalize one preformatted H.8 DDP CSV package to canonical H.8 columns."""

    raw = pd.read_csv(path, skiprows=5)
    if "Time Period" not in raw.columns:
        raise ValueError(f"H.8 DDP package missing Time Period column: {path}")

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(raw["Time Period"], errors="coerce")
    if out["date"].isna().any():
        raise ValueError(f"H.8 DDP package has unparseable Time Period values: {path}")
    out["bank_group"] = bank_group

    columns = list(raw.columns)
    for target, code_prefix in H8_DDP_LEVEL_CODES.items():
        source = _find_ddp_column(columns, code_prefix)
        out[target] = pd.to_numeric(raw[source], errors="coerce")
    out["h8_security_label"] = SECURITY_LABEL
    return out


def build_target_group_h8_input(
    input_dir: str | Path,
    output_path: str | Path | None = None,
    *,
    drop_incomplete: bool = True,
) -> pd.DataFrame:
    """Build one canonical long-form H.8 input from downloaded target-group packages."""

    frames = []
    in_dir = Path(input_dir)
    for package in target_packages():
        frames.append(normalize_h8_ddp_package(in_dir / package.filename, package.bank_group))
    out = pd.concat(frames, ignore_index=True).sort_values(["date", "bank_group"]).reset_index(drop=True)
    if drop_incomplete:
        required = list(H8_DDP_LEVEL_CODES)
        out = out.dropna(subset=required).reset_index(drop=True)
    if output_path is not None:
        write_csv(out, output_path)
    return out

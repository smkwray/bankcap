"""Small IO helpers used by the seed implementation."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterable
from pathlib import Path

import pandas as pd


def ensure_parent(path: str | Path) -> Path:
    """Create the parent directory for *path* and return a ``Path`` object."""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def read_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    """Read a CSV with a clear missing-file message."""

    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    return pd.read_csv(csv_path, **kwargs)


def write_csv(df: pd.DataFrame, path: str | Path) -> Path:
    """Write a dataframe to CSV, creating parent directories as needed."""

    out = ensure_parent(path)
    df.to_csv(out, index=False)
    return out


def copy_file(src: str | Path, dest: str | Path, *, overwrite: bool = False) -> Path:
    """Copy one file into a project-local destination."""

    src_path = Path(src)
    dest_path = ensure_parent(dest)
    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")
    if dest_path.exists() and not overwrite:
        raise FileExistsError(f"Destination exists; pass overwrite=True to replace it: {dest_path}")
    shutil.copy2(src_path, dest_path)
    return dest_path


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(project_root: str | Path, relative_path: str | Path) -> Path:
    """Resolve a config path relative to the project root.

    Absolute paths are returned unchanged; relative paths are joined to ``project_root``.
    """

    rel = Path(relative_path)
    if rel.is_absolute():
        return rel
    return Path(project_root) / rel


def first_existing(paths: Iterable[str | Path]) -> Path | None:
    """Return the first existing path from an iterable, or ``None``."""

    for path in paths:
        candidate = Path(path)
        if candidate.exists():
            return candidate
    return None

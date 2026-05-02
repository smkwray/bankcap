"""Lightweight table-schema contracts for seeded panels."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from bankcap.config import load_yaml
from bankcap.exceptions import SchemaError


@dataclass(frozen=True)
class ColumnSpec:
    """One column in a table schema."""

    name: str
    dtype: str
    required: bool = True
    allowed_values: tuple[Any, ...] = ()
    description: str = ""

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> ColumnSpec:
        return cls(
            name=str(mapping["name"]),
            dtype=str(mapping.get("dtype", "any")),
            required=bool(mapping.get("required", True)),
            allowed_values=tuple(mapping.get("allowed_values", []) or []),
            description=str(mapping.get("description", "")),
        )


@dataclass(frozen=True)
class TableSchema:
    """A lightweight dataframe schema."""

    name: str
    version: int
    primary_key: tuple[str, ...]
    claim_boundary: str
    columns: tuple[ColumnSpec, ...]

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> TableSchema:
        return cls(
            name=str(mapping["name"]),
            version=int(mapping.get("version", 1)),
            primary_key=tuple(mapping.get("primary_key", []) or []),
            claim_boundary=str(mapping.get("claim_boundary", "")),
            columns=tuple(ColumnSpec.from_mapping(c) for c in mapping.get("columns", [])),
        )

    @property
    def required_columns(self) -> list[str]:
        return [column.name for column in self.columns if column.required]


def load_table_schema(path: str | Path) -> TableSchema:
    """Load a schema YAML file."""

    return TableSchema.from_mapping(load_yaml(path))


def _is_bool_like(series: pd.Series) -> bool:
    if pd.api.types.is_bool_dtype(series):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return True
    lowered = {str(value).strip().lower() for value in non_null.unique()}
    return lowered.issubset({"true", "false", "0", "1", "yes", "no"})


def _dtype_issue(series: pd.Series, expected: str) -> str | None:
    expected = expected.lower()
    if expected in {"any", "object"}:
        return None
    if expected == "numeric" and not pd.api.types.is_numeric_dtype(series):
        coerced = pd.to_numeric(series, errors="coerce")
        if coerced.notna().sum() < series.notna().sum():
            return "expected numeric"
    if expected == "datetime":
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().sum() < series.notna().sum():
            return "expected datetime-compatible"
    if expected == "bool" and not _is_bool_like(series):
        return "expected boolean-compatible"
    if expected == "string":
        # Anything can be stringified; reject only fully numeric columns to catch obvious mixups.
        return None
    return None


def validate_dataframe(
    df: pd.DataFrame,
    schema: TableSchema,
    *,
    allow_extra: bool = True,
    check_primary_key: bool = True,
) -> list[str]:
    """Validate a dataframe against a lightweight schema and return issues."""

    issues: list[str] = []
    columns = set(df.columns)
    for column in schema.columns:
        if column.required and column.name not in columns:
            issues.append(f"missing required column: {column.name}")
            continue
        if column.name not in columns:
            continue
        dtype_issue = _dtype_issue(df[column.name], column.dtype)
        if dtype_issue:
            issues.append(f"column {column.name}: {dtype_issue}")
        if column.allowed_values:
            allowed = set(column.allowed_values)
            observed = set(df[column.name].dropna().unique())
            if column.dtype == "bool":
                # Normalize booleans before comparing.
                observed = {bool(value) for value in observed if value in {True, False}}
            unexpected = sorted(str(value) for value in observed if value not in allowed)
            if unexpected:
                issues.append(f"column {column.name}: unexpected values {unexpected}")

    if not allow_extra:
        known = {column.name for column in schema.columns}
        extra = sorted(columns.difference(known))
        if extra:
            issues.append(f"unexpected extra columns: {extra}")

    if check_primary_key and schema.primary_key:
        missing_pk = [column for column in schema.primary_key if column not in columns]
        if missing_pk:
            issues.append(f"primary-key columns missing: {missing_pk}")
        elif df.duplicated(list(schema.primary_key)).any():
            issues.append(f"duplicate rows under primary key: {list(schema.primary_key)}")

    return issues


def validate_csv(path: str | Path, schema_path: str | Path, *, allow_extra: bool = True) -> list[str]:
    """Read and validate a CSV against a schema path."""

    schema = load_table_schema(schema_path)
    df = pd.read_csv(path)
    return validate_dataframe(df, schema, allow_extra=allow_extra)


def assert_valid_dataframe(df: pd.DataFrame, schema: TableSchema, *, allow_extra: bool = True) -> None:
    """Raise ``SchemaError`` when ``df`` fails ``schema``."""

    issues = validate_dataframe(df, schema, allow_extra=allow_extra)
    if issues:
        raise SchemaError(f"{schema.name} failed validation: " + "; ".join(issues))

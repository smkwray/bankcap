"""Sibling source-contract loading, validation, and local import."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from bankcap.config import load_yaml
from bankcap.exceptions import ContractError
from bankcap.io import copy_file, resolve_project_path, sha256_file


@dataclass(frozen=True)
class ArtifactContract:
    """Contract for a single upstream artifact."""

    id: str
    path: str
    local_path: str
    required: bool
    frequency: str
    key_columns: tuple[str, ...]
    required_columns: tuple[str, ...]
    useful_columns: tuple[str, ...]
    accepted_column_aliases: dict[str, list[str]]

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> ArtifactContract:
        return cls(
            id=str(mapping["id"]),
            path=str(mapping["path"]),
            local_path=str(mapping.get("local_path") or mapping["path"]),
            required=bool(mapping.get("required", False)),
            frequency=str(mapping.get("frequency", "unknown")),
            key_columns=tuple(mapping.get("key_columns", []) or []),
            required_columns=tuple(mapping.get("required_columns", []) or []),
            useful_columns=tuple(mapping.get("useful_columns", []) or []),
            accepted_column_aliases={
                str(key): [str(value) for value in values]
                for key, values in (mapping.get("accepted_column_aliases", {}) or {}).items()
            },
        )


@dataclass(frozen=True)
class SourceContract:
    """Source contract for a sibling project."""

    project: str
    required_for_first_pass: bool
    default_source_root_env: str | None
    local_import_root: str
    role: str
    guardrails: tuple[str, ...]
    artifacts: tuple[ArtifactContract, ...]
    path: Path | None = None

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any], *, path: str | Path | None = None) -> SourceContract:
        return cls(
            project=str(mapping["project"]),
            required_for_first_pass=bool(mapping.get("required_for_first_pass", False)),
            default_source_root_env=mapping.get("default_source_root_env"),
            local_import_root=str(mapping.get("local_import_root", f"data/imported/{mapping['project']}")),
            role=str(mapping.get("role", "")),
            guardrails=tuple(mapping.get("guardrails", []) or []),
            artifacts=tuple(ArtifactContract.from_mapping(a) for a in mapping.get("artifacts", [])),
            path=Path(path) if path is not None else None,
        )


def load_source_contract(path: str | Path) -> SourceContract:
    """Load one source contract YAML file."""

    return SourceContract.from_mapping(load_yaml(path), path=path)


def load_source_contracts(contracts_dir: str | Path) -> dict[str, SourceContract]:
    """Load all ``*.yaml`` source contracts in a directory, keyed by sibling project name."""

    directory = Path(contracts_dir)
    if not directory.exists():
        raise ContractError(f"contracts directory not found: {directory}")
    contracts: dict[str, SourceContract] = {}
    for path in sorted(directory.glob("*.yaml")):
        contract = load_source_contract(path)
        contracts[contract.project] = contract
    return contracts


def resolve_source_root(contract: SourceContract, source_root: str | Path | None = None) -> Path | None:
    """Resolve a sibling source root from an explicit argument or environment variable."""

    if source_root:
        return Path(source_root)
    if contract.default_source_root_env:
        env_value = os.getenv(contract.default_source_root_env)
        if env_value:
            return Path(env_value)
    return None


def _artifact_source_path(
    artifact: ArtifactContract,
    *,
    contract: SourceContract,
    project_root: str | Path,
    source_root: str | Path | None,
    imported: bool,
) -> Path:
    if imported:
        return resolve_project_path(project_root, artifact.local_path)
    root = resolve_source_root(contract, source_root)
    if root is None:
        raise ContractError(
            f"No source root for {contract.project}; pass --source-root or set "
            f"{contract.default_source_root_env}"
        )
    return Path(root) / artifact.path


def validate_contract(
    contract: SourceContract,
    *,
    project_root: str | Path = ".",
    source_root: str | Path | None = None,
    imported: bool = False,
    required_only: bool = False,
    strict_columns: bool = False,
) -> list[str]:
    """Validate that expected sibling artifacts are available.

    By default this checks existence only. ``strict_columns`` reads CSV artifacts and verifies the
    minimal contract columns. Keep strictness optional because sibling outputs may evolve and useful
    columns are deliberately alias-tolerant.
    """

    issues: list[str] = []
    artifacts = [a for a in contract.artifacts if (a.required or not required_only)]
    for artifact in artifacts:
        try:
            path = _artifact_source_path(
                artifact,
                contract=contract,
                project_root=project_root,
                source_root=source_root,
                imported=imported,
            )
        except ContractError as exc:
            if artifact.required or contract.required_for_first_pass:
                issues.append(str(exc))
            continue

        if not path.exists():
            severity = "required" if artifact.required else "optional"
            issues.append(f"{contract.project}:{artifact.id} missing {severity} artifact: {path}")
            continue

        if strict_columns and path.suffix.lower() == ".csv" and artifact.required_columns:
            try:
                columns = set(pd.read_csv(path, nrows=5).columns)
            except Exception as exc:  # pragma: no cover - defensive branch
                issues.append(f"{contract.project}:{artifact.id} could not be read: {exc}")
                continue
            missing = [column for column in artifact.required_columns if column not in columns]
            if missing:
                issues.append(
                    f"{contract.project}:{artifact.id} missing required columns {missing}; "
                    f"found {sorted(columns)}"
                )
    return issues


def import_contract_artifacts(
    contract: SourceContract,
    *,
    project_root: str | Path = ".",
    source_root: str | Path | None = None,
    required_only: bool = False,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Copy sibling artifacts into ignored project-local import paths.

    Returns a small manifest dataframe. The copied files remain local and ignored by git.
    """

    artifacts = [a for a in contract.artifacts if (a.required or not required_only)]
    rows: list[dict[str, object]] = []
    for artifact in artifacts:
        src = _artifact_source_path(
            artifact,
            contract=contract,
            project_root=project_root,
            source_root=source_root,
            imported=False,
        )
        dest = resolve_project_path(project_root, artifact.local_path)
        if not src.exists():
            if artifact.required:
                raise FileNotFoundError(f"Required artifact missing: {src}")
            rows.append(
                {
                    "project": contract.project,
                    "artifact_id": artifact.id,
                    "source_path": str(src),
                    "local_path": str(dest),
                    "copied": False,
                    "reason": "missing optional artifact",
                    "sha256": "",
                }
            )
            continue
        copied = copy_file(src, dest, overwrite=overwrite)
        rows.append(
            {
                "project": contract.project,
                "artifact_id": artifact.id,
                "source_path": str(src),
                "local_path": str(copied),
                "copied": True,
                "reason": "",
                "sha256": sha256_file(copied),
            }
        )
    return pd.DataFrame(rows)

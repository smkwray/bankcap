"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bankcap.exceptions import ConfigError
from bankcap.io import resolve_project_path

REQUIRED_PROJECT_KEYS = {
    "project",
    "primary_question",
    "first_milestone",
    "paths",
    "source_contracts",
    "schemas",
    "claim_boundary",
}


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""

    yaml_path = Path(path)
    if not yaml_path.exists():
        raise ConfigError(f"YAML file not found: {yaml_path}")
    with yaml_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Expected YAML mapping in {yaml_path}")
    return loaded


def project_root_from_config(config_path: str | Path) -> Path:
    """Infer project root from ``config/project.yaml`` style paths."""

    path = Path(config_path).resolve()
    if path.parent.name == "config":
        return path.parent.parent
    return path.parent


def load_project_config(config_path: str | Path = "config/project.yaml") -> dict[str, Any]:
    """Load the project-level config."""

    return load_yaml(config_path)


def validate_project_config(
    config_path: str | Path = "config/project.yaml", *, project_root: str | Path | None = None
) -> list[str]:
    """Return human-readable validation issues for the project config.

    The validator is intentionally conservative and file-oriented so a reviewer can quickly see which
    source contracts or schemas are missing after unzipping.
    """

    config_path = Path(config_path)
    root = Path(project_root) if project_root is not None else project_root_from_config(config_path)
    issues: list[str] = []
    try:
        cfg = load_project_config(config_path)
    except ConfigError as exc:
        return [str(exc)]

    missing = sorted(REQUIRED_PROJECT_KEYS.difference(cfg))
    for key in missing:
        issues.append(f"project config missing required key: {key}")

    if cfg.get("project") != "bankcap":
        issues.append("project config key 'project' should equal 'bankcap'")

    for rel in cfg.get("source_contracts", []) or []:
        path = resolve_project_path(root, rel)
        if not path.exists():
            issues.append(f"source contract not found: {rel}")

    schemas = cfg.get("schemas", {}) or {}
    if not isinstance(schemas, dict):
        issues.append("schemas must be a mapping of schema name to path")
    else:
        for schema_name, rel in schemas.items():
            path = resolve_project_path(root, rel)
            if not path.exists():
                issues.append(f"schema '{schema_name}' not found: {rel}")

    paths = cfg.get("paths", {}) or {}
    if not isinstance(paths, dict):
        issues.append("paths must be a mapping")
    else:
        for key in ("source_contracts", "schemas", "episodes"):
            if key not in paths:
                issues.append(f"paths missing key: {key}")

    claim_boundary = cfg.get("claim_boundary", []) or []
    if not isinstance(claim_boundary, list) or len(claim_boundary) < 4:
        issues.append("claim_boundary should list the H.8 and bank-level claim guardrails")

    return issues

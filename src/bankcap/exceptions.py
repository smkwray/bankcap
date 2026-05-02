"""Project-specific exceptions."""

from __future__ import annotations


class BankcapError(Exception):
    """Base exception for bankcap."""


class ConfigError(BankcapError):
    """Raised when project or source-contract configuration is invalid."""


class ContractError(BankcapError):
    """Raised when a sibling source contract is invalid or unsatisfied."""


class SchemaError(BankcapError):
    """Raised when a panel fails a schema contract."""

"""Structured API errors."""

from __future__ import annotations

from typing import Any


class DerivKitError(Exception):
    """Base exception for DerivKit."""


class DslValidationError(DerivKitError):
    """DSL schema validation failure with field-level errors."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        msg = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
        super().__init__(msg)


class PricingError(DerivKitError):
    """Pricing computation failure."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.details = details or {}
        super().__init__(message)

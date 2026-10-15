"""SEC Financial Intelligence Engine — Application exceptions."""

from __future__ import annotations
from typing import Any, Dict, Optional


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=404,
            detail={"resource": resource, "identifier": identifier},
        )


class ValidationError(AppError):
    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=422, detail=detail)


class SECClientError(AppError):
    """Error communicating with SEC EDGAR."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=502, detail=detail)


class IngestionError(AppError):
    """Error during filing ingestion pipeline."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=500, detail=detail)


class ProviderUnavailableError(AppError):
    """AI provider not configured or unreachable."""

    def __init__(self, provider: str):
        super().__init__(
            message=f"AI provider '{provider}' is not available. "
            "Configure the API key or switch providers.",
            status_code=503,
            detail={"provider": provider},
        )


class InsufficientEvidenceError(AppError):
    """Not enough evidence to answer a query."""

    def __init__(self, message: str = "Insufficient evidence to answer this question."):
        super().__init__(message=message, status_code=200)

"""Stable error model exports and SDK exceptions for connector authors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from connector_author_sdk.generated.error_models import ErrorEnvelope, ErrorPayload


@dataclass(frozen=True, slots=True)
class ConnectorError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": dict(self.details),
            }
        }

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class AuthInvalidError(ConnectorError):
    def __init__(self, message: str = "Authentication is invalid", **details: Any):
        super().__init__(code="auth_invalid", message=message, details=details)


class AuthExpiredError(ConnectorError):
    def __init__(self, message: str = "Authentication has expired", **details: Any):
        super().__init__(code="auth_expired", message=message, details=details)


class ProviderTimeoutError(ConnectorError):
    def __init__(self, message: str = "Provider request timed out", **details: Any):
        super().__init__(code="provider_timeout", message=message, details=details)


class ProviderRateLimitedError(ConnectorError):
    def __init__(self, message: str = "Provider rate limited the request", **details: Any):
        super().__init__(code="provider_rate_limited", message=message, details=details)


class ResourceNotFoundError(ConnectorError):
    def __init__(self, message: str = "Requested resource was not found", **details: Any):
        super().__init__(code="resource_not_found", message=message, details=details)


class InvalidRequestError(ConnectorError):
    def __init__(self, message: str = "Request is invalid", **details: Any):
        super().__init__(code="invalid_request", message=message, details=details)


class MisconfigurationError(ConnectorError):
    def __init__(self, message: str = "Connector configuration is invalid", **details: Any):
        super().__init__(code="misconfiguration", message=message, details=details)


class ProviderUnavailableError(ConnectorError):
    def __init__(self, message: str = "Provider is unavailable", **details: Any):
        super().__init__(code="provider_unavailable", message=message, details=details)


__all__ = [
    "AuthExpiredError",
    "AuthInvalidError",
    "ConnectorError",
    "ErrorEnvelope",
    "ErrorPayload",
    "InvalidRequestError",
    "MisconfigurationError",
    "ProviderRateLimitedError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "ResourceNotFoundError",
]

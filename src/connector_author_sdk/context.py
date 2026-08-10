"""Execution context types for connector authors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


class LoggerProtocol(Protocol):
    """Minimal logger surface required by connectors."""

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...


class HttpResponseProtocol(Protocol):
    """Minimal HTTP response surface required by connectors."""

    status_code: int

    def json(self) -> Any: ...

    @property
    def text(self) -> str: ...


class HttpClientProtocol(Protocol):
    """Controlled HTTP client surface injected by the runtime."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseProtocol: ...

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        data: Any = None,
        timeout: float | None = None,
    ) -> HttpResponseProtocol: ...


    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
        data: Any = None,
        timeout: float | None = None,
    ) -> HttpResponseProtocol: ...


class PlatformHttpClientProtocol(HttpClientProtocol, Protocol):
    """Runtime-controlled client for first-party internal platform APIs."""


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Resolved connector auth exposed to connector code."""

    auth_type: str
    values: Mapping[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


@dataclass(frozen=True, slots=True)
class ConnectorContext:
    """Runtime execution context passed to connector methods."""

    instance_id: str
    connector_key: str
    connector_version: str
    owner_type: str
    owner_id: str
    config: Mapping[str, Any] = field(default_factory=dict)
    auth: AuthContext = field(default_factory=lambda: AuthContext(auth_type="none"))
    logger: LoggerProtocol | None = None
    http: HttpClientProtocol | None = None
    platform_http: PlatformHttpClientProtocol | None = None
    project_id: str | None = None
    execution_id: str = ""

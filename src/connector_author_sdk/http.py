"""Concrete HTTP helpers for connector authors."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

from connector_author_sdk.errors import ProviderUnavailableError


DEFAULT_USER_AGENT = "orbixal-connector-author-sdk/0.1.1"


@dataclass(frozen=True, slots=True)
class ProviderHttpTelemetry:
    provider: str
    method: str
    outcome: str
    duration_ms: float
    status_code: int | None = None


class SimpleHttpResponse:
    """Small response wrapper aligned with the SDK protocol."""

    def __init__(self, response: httpx.Response):
        self._response = response
        self.status_code = response.status_code
        self.headers = dict(response.headers)

    @property
    def text(self) -> str:
        return self._response.text

    def json(self) -> Any:
        return self._response.json()


class SimpleHttpClient:
    """Default local HTTP client for connectors."""

    def __init__(self, *, user_agent: str = DEFAULT_USER_AGENT):
        self.user_agent = user_agent
        self._client = httpx.Client(headers={"User-Agent": user_agent})
        self._provider_telemetry: list[ProviderHttpTelemetry] = []

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: float | None = None,
        provider: str | None = None,
    ) -> SimpleHttpResponse:
        return self._request(
            "GET",
            url,
            headers=headers,
            params=params,
            timeout=timeout,
            provider=provider,
        )

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
        data: Any = None,
        timeout: float | None = None,
        provider: str | None = None,
    ) -> SimpleHttpResponse:
        return self._request(
            "POST",
            url,
            headers=headers,
            json=json,
            data=data,
            timeout=timeout,
            provider=provider,
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        data: Any = None,
        timeout: float | None = None,
        provider: str | None = None,
    ) -> SimpleHttpResponse:
        started = perf_counter()
        telemetry_provider = _provider_label(provider, url)
        try:
            response = self._client.request(
                method,
                url,
                headers=dict(headers or {}),
                params=params,
                json=json,
                data=data,
                timeout=timeout,
            )
            self._provider_telemetry.append(
                ProviderHttpTelemetry(
                    provider=telemetry_provider,
                    method=method,
                    outcome=_status_outcome(response.status_code),
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    status_code=response.status_code,
                )
            )
            return SimpleHttpResponse(response)
        except httpx.RequestError as exc:
            self._provider_telemetry.append(
                ProviderHttpTelemetry(
                    provider=telemetry_provider,
                    method=method,
                    outcome="transport_error",
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
            )
            raise ProviderUnavailableError(
                message=f"HTTP request failed: {exc}",
                url=url,
                method=method,
            ) from exc

    def consume_provider_telemetry(self) -> list[dict[str, Any]]:
        events = [
            {
                "provider": event.provider,
                "method": event.method,
                "outcome": event.outcome,
                "duration_ms": event.duration_ms,
                "status_code": event.status_code,
            }
            for event in self._provider_telemetry
        ]
        self._provider_telemetry.clear()
        return events


def _provider_label(provider: str | None, url: str) -> str:
    if provider and provider.strip():
        return provider.strip()
    parsed = urlparse(url)
    return parsed.netloc or parsed.path or "unknown"


def _status_outcome(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "success"
    if 400 <= status_code < 500:
        return "client_error"
    if 500 <= status_code < 600:
        return "server_error"
    return "other"


__all__ = ["DEFAULT_USER_AGENT", "ProviderHttpTelemetry", "SimpleHttpClient", "SimpleHttpResponse"]

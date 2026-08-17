"""Concrete HTTP helpers for connector authors."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, Self
from urllib.parse import urlparse

import httpx

from connector_author_sdk.errors import ProviderUnavailableError

DEFAULT_USER_AGENT = "orbixal-connector-author-sdk/0.1.4"


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

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        trust_env: bool = True,
    ):
        self.user_agent = user_agent
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            trust_env=trust_env,
        )
        self._provider_telemetry: list[ProviderHttpTelemetry] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._client.close()

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
        provider: str | None = None,
    ) -> SimpleHttpResponse:
        return self._request(
            method,
            url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            timeout=timeout,
            provider=provider,
        )

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


class GatewayHttpClient(SimpleHttpClient):
    """Provider HTTP client relayed through the trusted connector egress gateway."""

    def __init__(
        self,
        *,
        gateway_url: str,
        access_token: str,
        policy_digest: str,
    ) -> None:
        super().__init__(trust_env=False)
        self._gateway_url = _absolute_http_url(gateway_url, "gateway_url")
        self._access_token = _required(access_token, "access_token")
        self._policy_digest = _required(policy_digest, "policy_digest")

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
        payload: dict[str, Any] = {
            "method": method.upper(),
            "url": url,
            "headers": dict(headers or {}),
            "params": dict(params or {}),
            "json_body": dict(json) if json is not None else None,
            "policy_digest": self._policy_digest,
            "timeout_seconds": timeout,
        }
        if data is not None:
            raw_data = data.encode("utf-8") if isinstance(data, str) else bytes(data)
            payload["body_base64"] = base64.b64encode(raw_data).decode("ascii")
        try:
            gateway_response = self._client.post(
                self._gateway_url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                json=payload,
                timeout=timeout,
            )
            gateway_response.raise_for_status()
            envelope = gateway_response.json()
            response = httpx.Response(
                status_code=int(envelope["status_code"]),
                headers=envelope.get("headers") or {},
                content=base64.b64decode(envelope.get("body_base64") or ""),
            )
            self._provider_telemetry.append(
                ProviderHttpTelemetry(
                    provider=telemetry_provider,
                    method=method.upper(),
                    outcome=_status_outcome(response.status_code),
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    status_code=response.status_code,
                )
            )
            return SimpleHttpResponse(response)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            self._provider_telemetry.append(
                ProviderHttpTelemetry(
                    provider=telemetry_provider,
                    method=method.upper(),
                    outcome="transport_error",
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
            )
            raise ProviderUnavailableError(
                message="Connector egress gateway request failed.",
                url=url,
                method=method.upper(),
            ) from exc


class SimplePlatformHttpClient(SimpleHttpClient):
    """Pinned-origin client backed by a rotating execution access grant."""

    def __init__(
        self,
        *,
        access_token: str,
        token_expires_at: str,
        renewal_url: str,
        renewal_handle: str,
        absolute_expires_at: str,
        audience: str,
        service_base_url: str,
        project_id: str,
        renewal_skew_seconds: int = 60,
    ) -> None:
        super().__init__()
        self._access_token = _required(access_token, "access_token")
        self._token_expires_at = _parse_datetime(token_expires_at)
        self._renewal_url = _absolute_https_url(renewal_url, "renewal_url")
        self._renewal_handle = _required(renewal_handle, "renewal_handle")
        self._absolute_expires_at = _parse_datetime(absolute_expires_at)
        self._audience = _required(audience, "audience")
        self._service_base_url = _absolute_https_url(
            service_base_url, "service_base_url"
        ).rstrip("/")
        self._project_id = _required(project_id, "project_id")
        self._renewal_skew = timedelta(seconds=max(renewal_skew_seconds, 0))

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
        request_url = self._resolve_path(url)
        self._renew_if_needed()
        supplied_headers = {key.lower(): value for key, value in (headers or {}).items()}
        if "authorization" in supplied_headers or "x-orbixal-project-id" in supplied_headers:
            raise ValueError("Platform authorization and project headers are runtime-owned.")
        runtime_headers = {
            **dict(headers or {}),
            "Authorization": f"Bearer {self._access_token}",
            "X-Orbixal-Project-Id": self._project_id,
        }
        return super()._request(
            method,
            request_url,
            headers=runtime_headers,
            params=params,
            json=json,
            data=data,
            timeout=timeout,
            provider=provider or "orbixal-platform",
        )

    def _resolve_path(self, path: str) -> str:
        parsed = urlparse(path)
        if parsed.scheme or parsed.netloc or not path.startswith("/"):
            raise ValueError("Platform HTTP requests require an absolute path, not a URL.")
        return f"{self._service_base_url}{path}"

    def _renew_if_needed(self) -> None:
        now = datetime.now(UTC)
        if now + self._renewal_skew < self._token_expires_at:
            return
        if now >= self._absolute_expires_at:
            raise ProviderUnavailableError(
                message="Connector execution platform access expired.",
                url=self._renewal_url,
                method="POST",
            )
        response = self._client.post(
            self._renewal_url,
            json={"renewal_handle": self._renewal_handle},
            timeout=10.0,
        )
        if response.status_code != 200:
            raise ProviderUnavailableError(
                message="Connector execution platform access renewal failed.",
                url=self._renewal_url,
                method="POST",
            )
        payload = response.json()
        if (
            not isinstance(payload, dict)
            or payload.get("audience") != self._audience
            or str(payload.get("service_base_url") or "").rstrip("/")
            != self._service_base_url
            or _parse_datetime(str(payload.get("absolute_expires_at") or ""))
            != self._absolute_expires_at
            or str(payload.get("renewal_url") or "") != self._renewal_url
        ):
            raise ProviderUnavailableError(
                message="Connector execution platform access renewal changed its scope.",
                url=self._renewal_url,
                method="POST",
            )
        self._access_token = _required(str(payload.get("access_token") or ""), "access_token")
        self._token_expires_at = _parse_datetime(str(payload.get("token_expires_at") or ""))
        self._renewal_handle = _required(
            str(payload.get("renewal_handle") or ""), "renewal_handle"
        )


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


def _required(value: str, name: str) -> str:
    if not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Platform access timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("Platform access timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _absolute_https_url(value: str, name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute HTTPS URL")
    return value


def _absolute_http_url(value: str, name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute HTTP(S) URL")
    return value


__all__ = [
    "DEFAULT_USER_AGENT",
    "ProviderHttpTelemetry",
    "SimpleHttpClient",
    "SimpleHttpResponse",
    "SimplePlatformHttpClient",
]

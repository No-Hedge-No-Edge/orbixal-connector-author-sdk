"""Concrete HTTP helpers for connector authors."""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from connector_author_sdk.errors import ProviderUnavailableError


DEFAULT_USER_AGENT = "orbixal-connector-author-sdk/0.1.1"


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

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> SimpleHttpResponse:
        return self._request("GET", url, headers=headers, params=params, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
        data: Any = None,
        timeout: float | None = None,
    ) -> SimpleHttpResponse:
        return self._request(
            "POST",
            url,
            headers=headers,
            json=json,
            data=data,
            timeout=timeout,
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
    ) -> SimpleHttpResponse:
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
            return SimpleHttpResponse(response)
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(
                message=f"HTTP request failed: {exc}",
                url=url,
                method=method,
            ) from exc


__all__ = ["DEFAULT_USER_AGENT", "SimpleHttpClient", "SimpleHttpResponse"]

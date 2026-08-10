from datetime import UTC, datetime, timedelta

import httpx
import pytest

from connector_author_sdk.http import SimplePlatformHttpClient


def timestamp(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()


def make_client(*, token_expires_in: int = 300) -> SimplePlatformHttpClient:
    return SimplePlatformHttpClient(
        access_token="initial-token",
        token_expires_at=timestamp(token_expires_in),
        renewal_url="https://invocation.internal/api/v1/internal/executions/exec-1/platform-access/renew",
        renewal_handle="h" * 48,
        absolute_expires_at=timestamp(600),
        audience="nhne-connector-context",
        service_base_url="https://context.internal",
        project_id="project-1",
    )


def test_platform_client_pins_origin_and_runtime_headers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = make_client()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    response = client.get("/portfolio", params={"symbol": "AAPL"})

    assert response.status_code == 200
    assert str(requests[0].url) == "https://context.internal/portfolio?symbol=AAPL"
    assert requests[0].headers["Authorization"] == "Bearer initial-token"
    assert requests[0].headers["X-Orbixal-Project-Id"] == "project-1"


def test_platform_client_rejects_external_url_and_header_override() -> None:
    client = make_client()
    with pytest.raises(ValueError, match="absolute path"):
        client.get("https://attacker.example/steal")
    with pytest.raises(ValueError, match="runtime-owned"):
        client.get("/portfolio", headers={"Authorization": "Bearer attacker"})


def test_platform_client_renews_and_rotates_handle() -> None:
    requests: list[httpx.Request] = []
    absolute_expiry = timestamp(600)
    client = SimplePlatformHttpClient(
        access_token="initial-token",
        token_expires_at=timestamp(1),
        renewal_url="https://invocation.internal/api/v1/internal/executions/exec-1/platform-access/renew",
        renewal_handle="h" * 48,
        absolute_expires_at=absolute_expiry,
        audience="nhne-connector-context",
        service_base_url="https://context.internal",
        project_id="project-1",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "invocation.internal":
            return httpx.Response(
                200,
                json={
                    "access_token": "renewed-token",
                    "token_expires_at": timestamp(300),
                    "renewal_url": str(request.url),
                    "renewal_handle": "r" * 48,
                    "absolute_expires_at": absolute_expiry,
                    "audience": "nhne-connector-context",
                    "service_base_url": "https://context.internal",
                },
            )
        return httpx.Response(200, json={"ok": True})

    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.get("/portfolio")

    assert len(requests) == 2
    assert requests[1].headers["Authorization"] == "Bearer renewed-token"

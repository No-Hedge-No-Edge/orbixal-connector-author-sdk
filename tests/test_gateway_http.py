import base64

import httpx
import pytest

from connector_author_sdk.http import GatewayHttpClient


def test_gateway_http_preserves_provider_request_shape() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "status_code": 201,
                "headers": {"content-type": "application/json"},
                "body_base64": base64.b64encode(b'{"created":true}').decode(),
            },
        )

    client = GatewayHttpClient(
        gateway_url="https://egress.internal/api/v1/egress/request",
        access_token="execution-token",
        policy_digest="a" * 64,
    )
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    response = client.post(
        "https://api.example.com/v1/items",
        headers={"X-Provider-Key": "secret"},
        json={"name": "item"},
    )

    assert response.status_code == 201
    assert response.json() == {"created": True}
    assert requests[0].headers["Authorization"] == "Bearer execution-token"
    payload = requests[0].read().decode()
    assert '"url":"https://api.example.com/v1/items"' in payload
    assert '"policy_digest":"' + "a" * 64 + '"' in payload


def test_gateway_http_accepts_private_http_runtime_url() -> None:
    client = GatewayHttpClient(
        gateway_url="http://egress.internal:8080/api/v1/egress/request",
        access_token="execution-token",
        policy_digest="a" * 64,
    )

    assert client._gateway_url == "http://egress.internal:8080/api/v1/egress/request"


@pytest.mark.parametrize(
    "gateway_url",
    ["/api/v1/egress/request", "ftp://egress.internal/api/v1/egress/request"],
)
def test_gateway_http_rejects_non_http_absolute_urls(gateway_url: str) -> None:
    with pytest.raises(ValueError, match=r"absolute HTTP\(S\) URL"):
        GatewayHttpClient(
            gateway_url=gateway_url,
            access_token="execution-token",
            policy_digest="a" * 64,
        )

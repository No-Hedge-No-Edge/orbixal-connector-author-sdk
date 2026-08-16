import base64

import httpx

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

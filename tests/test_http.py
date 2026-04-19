import unittest
from unittest.mock import patch

import httpx

from connector_author_sdk.errors import ProviderUnavailableError
from connector_author_sdk.http import SimpleHttpClient


class HttpTests(unittest.TestCase):
    def test_get_json(self) -> None:
        with patch(
            "connector_author_sdk.http.httpx.Client.request",
            return_value=httpx.Response(
                status_code=200,
                json={"ok": True},
                request=httpx.Request("GET", "https://example.test/items"),
            ),
        ) as mock_request:
            response = SimpleHttpClient().get("https://example.test/items", params={"q": "ok"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(mock_request.call_args.kwargs["params"], {"q": "ok"})

    def test_post_json(self) -> None:
        with patch(
            "connector_author_sdk.http.httpx.Client.request",
            return_value=httpx.Response(
                status_code=200,
                json={"hello": "world"},
                request=httpx.Request("POST", "https://example.test/echo"),
            ),
        ) as mock_request:
            response = SimpleHttpClient().post(
                "https://example.test/echo",
                json={"hello": "world"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hello"], "world")
        self.assertEqual(mock_request.call_args.args[0], "POST")
        self.assertEqual(mock_request.call_args.kwargs["json"], {"hello": "world"})

    def test_request_error_becomes_provider_unavailable(self) -> None:
        request = httpx.Request("GET", "https://example.test/down")
        with patch(
            "connector_author_sdk.http.httpx.Client.request",
            side_effect=httpx.RequestError("boom", request=request),
        ):
            with self.assertRaises(ProviderUnavailableError):
                SimpleHttpClient().get("https://example.test/down")

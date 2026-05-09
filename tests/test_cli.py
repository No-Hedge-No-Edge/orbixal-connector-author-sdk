import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from contextlib import redirect_stdout

import httpx

from connector_author_sdk.cli import main, publish_local_package
from connector_author_sdk.errors import ConnectorError


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


class CliTests(unittest.TestCase):
    def test_validate_command(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "validate",
                    "--connector",
                    "fake_connector:FakeConnector",
                    "--config",
                    '{"workspace":"orbixal"}',
                    "--auth",
                    '{"access_token":"token"}',
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["valid"])

    def test_run_query_command(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "run",
                    "query",
                    "--connector",
                    "fake_connector:FakeConnector",
                    "--action",
                    "search_issues",
                    "--params",
                    '{"query":"bug"}',
                    "--config",
                    '{"workspace":"orbixal"}',
                    "--auth",
                    '{"access_token":"token"}',
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "tabular")
        self.assertEqual(payload["meta"]["connector_key"], "fake")
        self.assertEqual(payload["meta"]["action"], "search_issues")
        self.assertEqual(payload["rows"][0]["values"]["query"], "bug")

    def test_publish_local_package_submits_and_approves(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path.endswith("/publication-submissions/local-package"):
                return httpx.Response(
                    201,
                    json={
                        "id": "sub_123",
                        "status": "validated",
                        "package_checksum": "a" * 64,
                    },
                )
            self.assertTrue(request.url.path.endswith("/publication-submissions/sub_123/approve"))
            return httpx.Response(
                200,
                json={
                    "id": "sub_123",
                    "status": "approved",
                    "package_ref": "artifact://connectors/fake/1.0.0/" + ("a" * 64),
                },
            )

        with TemporaryDirectory() as tmp_dir:
            client = httpx.Client(transport=httpx.MockTransport(handler))
            result = publish_local_package(
                package_dir=Path(tmp_dir),
                registry_url="http://registry.test/api/v1/",
                actor_type="user",
                actor_id="admin_123",
                approve=True,
                http_client=client,
            )

        self.assertEqual(result["submission"]["status"], "validated")
        self.assertEqual(result["approval"]["status"], "approved")
        self.assertEqual(len(requests), 2)
        submit_payload = json.loads(requests[0].content)
        self.assertEqual(submit_payload["publisher_type"], "first_party")
        self.assertEqual(submit_payload["actor_id"], "admin_123")
        approve_payload = json.loads(requests[1].content)
        self.assertTrue(approve_payload["set_as_default"])
        self.assertTrue(approve_payload["set_as_latest"])

    def test_publish_local_package_reports_registry_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "package invalid"})

        with TemporaryDirectory() as tmp_dir:
            client = httpx.Client(transport=httpx.MockTransport(handler))
            with self.assertRaises(ConnectorError) as exc_info:
                publish_local_package(
                    package_dir=Path(tmp_dir),
                    registry_url="http://registry.test/api/v1",
                    http_client=client,
                )

        self.assertEqual(exc_info.exception.code, "registry_publication_failed")
        self.assertEqual(exc_info.exception.message, "package invalid")

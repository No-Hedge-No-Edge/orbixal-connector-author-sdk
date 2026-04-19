import sys
from pathlib import Path
import unittest

from connector_author_sdk.harness import (
    build_context,
    describe_connector,
    load_connector,
    run_list_resources,
    run_query,
    run_read,
    run_test_connection,
    validate_connector,
)


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


class HarnessTests(unittest.TestCase):
    def test_load_connector_and_describe(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        manifest = describe_connector(connector)
        self.assertEqual(manifest["key"], "fake")
        self.assertEqual(manifest["operations"][0]["name"], "get_issue")

    def test_validate_connector_reports_valid_config(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        report = validate_connector(
            connector,
            config={"workspace": "orbixal"},
            auth_payload={"access_token": "token"},
        )
        self.assertTrue(report.valid)

    def test_validate_connector_reports_semantic_failure(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        report = validate_connector(
            connector,
            config={"workspace": "invalid"},
            auth_payload={"access_token": "token"},
        )
        self.assertFalse(report.valid)
        self.assertEqual(report.config_semantic.errors[0].field, "workspace")

    def test_build_context_uses_manifest_defaults(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        ctx = build_context(
            connector,
            config={"workspace": "orbixal"},
            auth_payload={"access_token": "token"},
        )
        self.assertEqual(ctx.connector_key, "fake")
        self.assertEqual(ctx.connector_version, "1.0.0")
        self.assertEqual(ctx.auth.get("access_token"), "token")

    def test_run_test_connection(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        result = run_test_connection(
            connector,
            config={"workspace": "orbixal"},
            auth_payload={"access_token": "token"},
        )
        self.assertTrue(result["success"])

    def test_run_list_resources(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        result = run_list_resources(
            connector,
            config={"workspace": "orbixal"},
            auth_payload={"access_token": "token"},
        )
        self.assertEqual(result["items"][0]["attributes"]["workspace"], "orbixal")

    def test_run_read_normalizes_records(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        result = run_read(
            connector,
            action="get_issue",
            params={"issue_number": 42},
            config={"workspace": "orbixal"},
            auth_payload={"access_token": "token"},
            include_raw=True,
        )
        self.assertEqual(result["kind"], "records")
        self.assertEqual(result["records"][0]["id"], "42")
        self.assertEqual(result["meta"]["connector_key"], "fake")
        self.assertEqual(result["meta"]["connector_version"], "1.0.0")
        self.assertEqual(result["meta"]["action"], "get_issue")
        self.assertEqual(result["meta"]["request_id"], "local-execution")
        self.assertEqual(result["raw"]["action"], "get_issue")

    def test_run_query_normalizes_tabular(self) -> None:
        connector = load_connector("fake_connector:FakeConnector")
        result = run_query(
            connector,
            action="search_issues",
            params={"query": "bug"},
            config={"workspace": "orbixal"},
            auth_payload={"access_token": "token"},
            cursor="cursor-1",
            include_raw=True,
        )
        self.assertEqual(result["kind"], "tabular")
        self.assertEqual(result["rows"][0]["values"]["query"], "bug")
        self.assertEqual(result["meta"]["action"], "search_issues")
        self.assertEqual(result["meta"]["request_id"], "local-execution")
        self.assertEqual(result["raw"]["cursor"], "cursor-1")

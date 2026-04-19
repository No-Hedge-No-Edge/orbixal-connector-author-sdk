import io
import json
import sys
from pathlib import Path
import unittest
from contextlib import redirect_stdout

from connector_author_sdk.cli import main


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

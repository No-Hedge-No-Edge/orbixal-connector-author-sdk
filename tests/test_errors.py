import io
import json
from contextlib import redirect_stderr
import unittest

from connector_author_sdk.cli import main
from connector_author_sdk.errors import AuthInvalidError


class ErrorTests(unittest.TestCase):
    def test_connector_error_to_dict(self) -> None:
        error = AuthInvalidError(provider="github")
        payload = error.to_dict()
        self.assertEqual(payload["error"]["code"], "auth_invalid")
        self.assertEqual(payload["error"]["details"]["provider"], "github")

    def test_cli_emits_structured_error(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["describe", "--connector", "missing_module:MissingConnector"])
        payload = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"]["code"], "sdk_error")

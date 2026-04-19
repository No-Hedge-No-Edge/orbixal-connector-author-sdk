import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from connector_author_sdk.cli import main
from connector_author_sdk.scaffold import scaffold_connector


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_connector(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            artifact = scaffold_connector(
                connector_key="sample_api",
                output_dir=tmp_dir,
            )
            self.assertTrue(Path(artifact.connector_file).exists())
            self.assertTrue(Path(artifact.pyproject_file).exists())
            self.assertEqual(artifact.class_name, "SampleApiConnector")

    def test_cli_init_command(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "init",
                        "--connector-key",
                        "sample_api",
                        "--output-dir",
                        tmp_dir,
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["connector_key"], "sample_api")
            self.assertEqual(stderr.getvalue(), "")

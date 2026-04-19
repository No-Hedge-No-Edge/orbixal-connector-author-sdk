import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from connector_author_sdk.packaging import (
    build_package_metadata,
    export_manifest,
    package_connector,
)


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from fake_connector import FakeConnector


class PackagingTests(unittest.TestCase):
    def test_build_package_metadata(self) -> None:
        metadata = build_package_metadata(
            FakeConnector(),
            connector_target="fake_connector:FakeConnector",
        )
        self.assertEqual(metadata["connector_key"], "fake")
        self.assertEqual(metadata["operations"][0]["name"], "get_issue")

    def test_export_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            manifest_path = export_manifest(
                FakeConnector(),
                Path(tmp_dir) / "manifest.json",
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["key"], "fake")

    def test_package_connector(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            artifact = package_connector(
                FakeConnector(),
                connector_target="fake_connector:FakeConnector",
                output_dir=tmp_dir,
            )
            manifest_payload = json.loads(
                Path(artifact.manifest_path).read_text(encoding="utf-8")
            )
            metadata_payload = json.loads(
                Path(artifact.metadata_path).read_text(encoding="utf-8")
            )
            checksums_payload = json.loads(
                Path(artifact.checksums_path).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest_payload["key"], "fake")
            self.assertEqual(
                metadata_payload["connector_target"],
                "fake_connector:FakeConnector",
            )
            self.assertEqual(metadata_payload["bundle_format_version"], "1")
            self.assertEqual(checksums_payload["algorithm"], "sha256")
            self.assertIn("manifest.json", checksums_payload["files"])
            self.assertEqual(Path(artifact.output_dir).name, "1.0.0")

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
import zipfile

from connector_author_sdk.packaging import (
    CODE_ARCHIVE_FILENAME,
    build_package_metadata,
    export_manifest,
    inspect_package_artifact,
    load_packaged_connector,
    package_connector,
    verify_package_artifact,
    verify_package_checksums,
    write_release_gate_metadata,
)


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from fake_connector import FakeConnector  # noqa: E402


class PackagingTests(unittest.TestCase):
    def test_build_package_metadata(self) -> None:
        metadata = build_package_metadata(
            FakeConnector(),
            connector_target="fake_connector:FakeConnector",
        )
        self.assertEqual(metadata["connector_key"], "fake")
        self.assertEqual(metadata["operations"][0]["name"], "get_issue")
        self.assertEqual(metadata["bundle_format_version"], "2")
        self.assertEqual(metadata["runtime_load"]["code_archive"], CODE_ARCHIVE_FILENAME)

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
            self.assertEqual(metadata_payload["bundle_format_version"], "2")
            self.assertEqual(
                metadata_payload["code_archive"]["path"],
                CODE_ARCHIVE_FILENAME,
            )
            self.assertEqual(checksums_payload["algorithm"], "sha256")
            self.assertIn("manifest.json", checksums_payload["files"])
            self.assertIn(CODE_ARCHIVE_FILENAME, checksums_payload["files"])
            self.assertEqual(Path(artifact.output_dir).name, "1.0.0")
            with zipfile.ZipFile(artifact.code_archive_path) as archive:
                self.assertIn("fake_connector.py", archive.namelist())

            inspected = inspect_package_artifact(artifact.output_dir)
            self.assertEqual(inspected["connector_key"], "fake")
            self.assertIn(CODE_ARCHIVE_FILENAME, inspected["checksums"]["files"])

    def test_write_release_gate_metadata_refreshes_checksums_and_signature(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            artifact = package_connector(
                FakeConnector(),
                connector_target="fake_connector:FakeConnector",
                output_dir=tmp_dir,
                signing_secret="secret",
                signing_key_id="test",
            )

            metadata = write_release_gate_metadata(
                artifact.output_dir,
                signing_secret="secret",
                signing_key_id="test",
                source_ref="git+https://github.com/orbixal/fake@abc123",
            )

            verify_package_checksums(artifact.output_dir)
            for path_key in (
                "vulnerability_scan_path",
                "malware_scan_path",
                "provenance_path",
                "egress_policy_path",
                "signature_path",
            ):
                self.assertTrue(Path(str(metadata[path_key])).is_file())

            vulnerability_scan = json.loads(
                Path(str(metadata["vulnerability_scan_path"])).read_text(encoding="utf-8")
            )
            provenance = json.loads(
                Path(str(metadata["provenance_path"])).read_text(encoding="utf-8")
            )
            self.assertEqual(
                vulnerability_scan["signature"]["signed_payload"],
                "scan_attestation.v1",
            )
            self.assertEqual(provenance["signature"]["signed_payload"], "provenance.v1")

    def test_load_packaged_connector_from_code_archive(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            source_root = Path(tmp_dir) / "src"
            package_dir = source_root / "packaged_fake"
            package_dir.mkdir(parents=True)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_dir / "connector.py").write_text(
                """
from typing import Any, Mapping

from connector_author_sdk import (
    ConnectionTestResult,
    Connector,
    ConnectorContext,
    ReadRequest,
    QueryRequest,
    RecordsResult,
    RecordItem,
    ResourcePage,
    ValidationResult,
    build_manifest,
    no_egress,
    no_auth,
    read_operation,
)


class PackagedConnector(Connector):
    def describe(self):
        return build_manifest(
            key="packaged_fake",
            name="Packaged Fake",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get"],
            auth_schema=no_auth(),
            egress_policy=no_egress(),
            config_schema={"type": "object"},
            resource_types=["item"],
            operations=[read_operation(name="get_item", input_schema={"type": "object"})],
        )

    def validate_config(self, config: Mapping[str, Any]) -> ValidationResult:
        return ValidationResult.ok()

    def test_connection(self, ctx: ConnectorContext) -> ConnectionTestResult:
        return ConnectionTestResult(success=True, summary="ok")

    def list_resources(self, ctx: ConnectorContext, query: Mapping[str, Any] | None = None):
        return ResourcePage(items=[])

    def read(self, ctx: ConnectorContext, request: ReadRequest):
        return RecordsResult(records=[RecordItem(id="1", type="item")])

    def query(self, ctx: ConnectorContext, request: QueryRequest):
        return RecordsResult(records=[])
""".lstrip(),
                encoding="utf-8",
            )

            sys.path.insert(0, str(source_root))
            try:
                from connector_author_sdk.harness import load_connector

                connector = load_connector("packaged_fake.connector:PackagedConnector")
                artifact = package_connector(
                    connector,
                    connector_target="packaged_fake.connector:PackagedConnector",
                    output_dir=Path(tmp_dir) / "dist",
                    source_paths=[package_dir],
                )
            finally:
                sys.path.remove(str(source_root))
                sys.modules.pop("packaged_fake.connector", None)
                sys.modules.pop("packaged_fake", None)

            loaded_connector = load_packaged_connector(artifact.output_dir)
            self.assertEqual(loaded_connector.describe().key, "packaged_fake")
            verification = verify_package_artifact(artifact.output_dir)
            self.assertTrue(verification["valid"])
            self.assertEqual(verification["connector_key"], "packaged_fake")

    def test_verify_package_checksums_rejects_tampered_bundle(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            artifact = package_connector(
                FakeConnector(),
                connector_target="fake_connector:FakeConnector",
                output_dir=tmp_dir,
            )
            Path(artifact.manifest_path).write_text("{}", encoding="utf-8")

            with self.assertRaises(ValueError):
                verify_package_checksums(artifact.output_dir)

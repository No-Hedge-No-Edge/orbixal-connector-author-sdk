"""Packaging helpers for connector authors."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from connector_author_sdk.connector import Connector
from connector_author_sdk.validation import validate_manifest


@dataclass(frozen=True, slots=True)
class PackageArtifact:
    connector_target: str
    connector_key: str
    connector_version: str
    output_dir: str
    manifest_path: str
    metadata_path: str
    checksums_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "connector_target": self.connector_target,
            "connector_key": self.connector_key,
            "connector_version": self.connector_version,
            "output_dir": self.output_dir,
            "manifest_path": self.manifest_path,
            "metadata_path": self.metadata_path,
            "checksums_path": self.checksums_path,
        }


def _sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8192):
            digest.update(chunk)
    return digest.hexdigest()


def build_package_metadata(
    connector: Connector,
    *,
    connector_target: str,
) -> dict[str, Any]:
    manifest = connector.describe()
    return {
        "bundle_format_version": "1",
        "connector_target": connector_target,
        "connector_key": manifest.key,
        "connector_version": manifest.version,
        "manifest_schema_version": manifest.manifest_schema_version,
        "sdk_version": manifest.sdk_version,
        "runtime_compatibility_range": manifest.runtime_compatibility_range,
        "resource_types": list(manifest.resource_types),
        "operations": [
            {"name": operation.name, "kind": operation.kind}
            for operation in manifest.operations
        ],
    }


def export_manifest(
    connector: Connector,
    output_path: str | Path,
    *,
    validate: bool = True,
) -> Path:
    manifest = connector.describe()
    if validate:
        validation_result = validate_manifest(manifest)
        if not validation_result.valid:
            raise ValueError(
                "Connector manifest is invalid and cannot be exported: "
                f"{validation_result.errors!r}"
            )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def package_connector(
    connector: Connector,
    *,
    connector_target: str,
    output_dir: str | Path,
) -> PackageArtifact:
    manifest = connector.describe()
    output_path = Path(output_dir) / manifest.key / manifest.version
    output_path.mkdir(parents=True, exist_ok=True)

    manifest_path = export_manifest(
        connector,
        output_path / "manifest.json",
        validate=True,
    )
    metadata_path = output_path / "package_metadata.json"
    metadata_path.write_text(
        json.dumps(
            build_package_metadata(
                connector,
                connector_target=connector_target,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    checksums_path = output_path / "checksums.json"
    checksums_path.write_text(
        json.dumps(
            {
                "algorithm": "sha256",
                "files": {
                    "manifest.json": _sha256_hex(manifest_path),
                    "package_metadata.json": _sha256_hex(metadata_path),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return PackageArtifact(
        connector_target=connector_target,
        connector_key=manifest.key,
        connector_version=manifest.version,
        output_dir=str(output_path),
        manifest_path=str(manifest_path),
        metadata_path=str(metadata_path),
        checksums_path=str(checksums_path),
    )


__all__ = [
    "PackageArtifact",
    "build_package_metadata",
    "export_manifest",
    "package_connector",
]

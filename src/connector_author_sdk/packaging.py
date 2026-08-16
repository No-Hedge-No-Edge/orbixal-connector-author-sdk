"""Packaging helpers for connector authors."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import hmac
from importlib import import_module
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any
import zipfile

from connector_author_sdk.connector import Connector
from connector_author_sdk.validation import validate_manifest, validate_package_metadata


BUNDLE_FORMAT_VERSION = "2"
CODE_ARCHIVE_FILENAME = "connector_code.zip"
SBOM_FILENAME = "sbom.json"
SIGNATURE_FILENAME = "signature.json"
VULNERABILITY_SCAN_FILENAME = "vulnerability_scan.json"
MALWARE_SCAN_FILENAME = "malware_scan.json"
PROVENANCE_FILENAME = "provenance.json"
EGRESS_POLICY_FILENAME = "egress_policy.json"
SIGNING_SECRET_ENV = "ORBIXAL_CONNECTOR_SIGNING_SECRET"
SCAN_ATTESTATION_SIGNED_PAYLOAD = "scan_attestation.v1"
PROVENANCE_SIGNED_PAYLOAD = "provenance.v1"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
EXCLUDED_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".python-version",
}
EXCLUDED_SUFFIXES = {
    ".key",
    ".pem",
    ".pyc",
    ".pyo",
}


@dataclass(frozen=True, slots=True)
class PackageArtifact:
    connector_target: str
    connector_key: str
    connector_version: str
    output_dir: str
    manifest_path: str
    metadata_path: str
    code_archive_path: str
    checksums_path: str
    sbom_path: str
    egress_policy_path: str
    signature_path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        payload: dict[str, str | None] = {
            "connector_target": self.connector_target,
            "connector_key": self.connector_key,
            "connector_version": self.connector_version,
            "output_dir": self.output_dir,
            "manifest_path": self.manifest_path,
            "metadata_path": self.metadata_path,
            "code_archive_path": self.code_archive_path,
            "checksums_path": self.checksums_path,
            "sbom_path": self.sbom_path,
            "egress_policy_path": self.egress_policy_path,
            "signature_path": self.signature_path,
        }
        return payload


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
    code_archive_filename: str = CODE_ARCHIVE_FILENAME,
    archive_members: Iterable[str] | None = None,
    signed: bool = False,
) -> dict[str, Any]:
    manifest = connector.describe()
    metadata = {
        "bundle_format_version": BUNDLE_FORMAT_VERSION,
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
        "runtime_load": {
            "entrypoint": connector_target,
            "code_archive": code_archive_filename,
        },
        "code_archive": {
            "path": code_archive_filename,
            "format": "zip",
            "members": sorted(archive_members or []),
        },
        "sbom": {
            "path": SBOM_FILENAME,
            "format": "cyclonedx-lite",
        },
    }
    if signed:
        metadata["signature"] = {
            "path": SIGNATURE_FILENAME,
            "algorithm": "hmac-sha256",
            "signed_payload": "checksums.v1",
        }
    return metadata


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
    source_paths: Iterable[str | Path] | None = None,
    dependencies: Iterable[str] | None = None,
    signing_secret: str | None = None,
    signing_key_id: str = "local-author",
) -> PackageArtifact:
    manifest = connector.describe()
    output_path = Path(output_dir) / manifest.key / manifest.version
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    resolved_source_paths = resolve_connector_source_paths(
        connector_target,
        source_paths=source_paths,
    )

    manifest_path = export_manifest(
        connector,
        output_path / "manifest.json",
        validate=True,
    )
    code_archive_path = output_path / CODE_ARCHIVE_FILENAME
    archive_members = write_code_archive(
        source_paths=resolved_source_paths,
        output_path=code_archive_path,
    )
    resolved_signing_secret = signing_secret or os.getenv(SIGNING_SECRET_ENV)
    metadata_path = output_path / "package_metadata.json"
    package_metadata = build_package_metadata(
        connector,
        connector_target=connector_target,
        archive_members=archive_members,
        signed=bool(resolved_signing_secret),
    )
    package_metadata_validation = validate_package_metadata(package_metadata)
    if not package_metadata_validation.valid:
        raise ValueError(
            "Connector package metadata is invalid and cannot be exported: "
            f"{package_metadata_validation.errors!r}"
        )
    metadata_path.write_text(
        json.dumps(
            package_metadata,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    sbom_path = output_path / SBOM_FILENAME
    sbom_path.write_text(
        json.dumps(
            build_sbom(connector, dependencies=dependencies),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    egress_policy_path = output_path / EGRESS_POLICY_FILENAME
    egress_policy_path.write_text(
        json.dumps(manifest.egress_policy.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksums_path = output_path / "checksums.json"
    checksums = {
        "algorithm": "sha256",
        "files": {
            "manifest.json": _sha256_hex(manifest_path),
            CODE_ARCHIVE_FILENAME: _sha256_hex(code_archive_path),
            "package_metadata.json": _sha256_hex(metadata_path),
            SBOM_FILENAME: _sha256_hex(sbom_path),
            EGRESS_POLICY_FILENAME: _sha256_hex(egress_policy_path),
        },
    }
    checksums_path.write_text(
        json.dumps(checksums, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    signature_path: Path | None = None
    if resolved_signing_secret:
        signature_path = output_path / SIGNATURE_FILENAME
        signature_path.write_text(
            json.dumps(
                build_signature(
                    connector=connector,
                    checksums=checksums,
                    signing_secret=resolved_signing_secret,
                    signing_key_id=signing_key_id,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        checksums["files"][SIGNATURE_FILENAME] = _sha256_hex(signature_path)
        checksums_path.write_text(
            json.dumps(checksums, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return PackageArtifact(
        connector_target=connector_target,
        connector_key=manifest.key,
        connector_version=manifest.version,
        output_dir=str(output_path),
        manifest_path=str(manifest_path),
        metadata_path=str(metadata_path),
        code_archive_path=str(code_archive_path),
        checksums_path=str(checksums_path),
        sbom_path=str(sbom_path),
        egress_policy_path=str(egress_policy_path),
        signature_path=str(signature_path) if signature_path else None,
    )


def build_sbom(
    connector: Connector,
    *,
    dependencies: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic lightweight CycloneDX-style SBOM."""

    manifest = connector.describe()
    dependency_components = [
        _dependency_component(dependency)
        for dependency in sorted({str(item).strip() for item in dependencies or [] if str(item).strip()})
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "metadata": {
            "component": {
                "type": "application",
                "name": manifest.key,
                "version": manifest.version,
            },
            "tools": [
                {
                    "vendor": "Orbixal",
                    "name": "orbixal-connector-author-sdk",
                    "version": manifest.sdk_version,
                }
            ],
        },
        "components": dependency_components,
    }


def build_signature(
    *,
    connector: Connector,
    checksums: dict[str, Any],
    signing_secret: str,
    signing_key_id: str,
) -> dict[str, Any]:
    """Build an HMAC signature over connector identity and file checksums."""

    if not signing_secret:
        raise ValueError("A non-empty signing_secret is required.")
    manifest = connector.describe()
    signed_payload = _signature_payload(
        connector_key=manifest.key,
        connector_version=manifest.version,
        checksums=checksums,
    )
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        _canonical_json(signed_payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "signature_format_version": "1",
        "algorithm": "hmac-sha256",
        "key_id": signing_key_id,
        "signed_payload": "checksums.v1",
        "signature": signature,
    }


def build_scan_attestation(
    connector: Connector,
    *,
    scanner_name: str,
    scanner_version: str | None = None,
    status: str = "passed",
    findings: Iterable[dict[str, Any]] | None = None,
    signing_secret: str | None = None,
    signing_key_id: str = "local-author",
) -> dict[str, Any]:
    """Build a signed scanner attestation for publication release gates."""

    manifest = connector.describe()
    attestation: dict[str, Any] = {
        "attestation_format_version": "1",
        "scanner": {
            "name": scanner_name,
        },
        "status": status,
        "subject": {
            "connector_key": manifest.key,
            "connector_version": manifest.version,
        },
        "findings": list(findings or []),
    }
    if scanner_version:
        attestation["scanner"]["version"] = scanner_version
    if signing_secret:
        attestation["signature"] = build_scan_attestation_signature(
            connector=connector,
            attestation=attestation,
            signing_secret=signing_secret,
            signing_key_id=signing_key_id,
        )
    return attestation


def build_scan_attestation_signature(
    *,
    connector: Connector,
    attestation: dict[str, Any],
    signing_secret: str,
    signing_key_id: str,
) -> dict[str, str]:
    """Build an HMAC signature over a scanner attestation."""

    if not signing_secret:
        raise ValueError("A non-empty signing_secret is required.")
    manifest = connector.describe()
    unsigned_attestation = json.loads(json.dumps(attestation))
    unsigned_attestation.pop("signature", None)
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        _canonical_json(
            {
                "connector_key": manifest.key,
                "connector_version": manifest.version,
                "scan_attestation": unsigned_attestation,
            }
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "algorithm": "hmac-sha256",
        "key_id": signing_key_id,
        "signed_payload": SCAN_ATTESTATION_SIGNED_PAYLOAD,
        "signature": signature,
    }


def build_provenance(
    connector: Connector,
    *,
    builder_id: str,
    source_ref: str | None = None,
    signing_secret: str | None = None,
    signing_key_id: str = "local-author",
) -> dict[str, Any]:
    """Build signed SLSA-style provenance metadata for a connector package."""

    manifest = connector.describe()
    provenance: dict[str, Any] = {
        "provenance_format_version": "1",
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": {
            "connector_key": manifest.key,
            "connector_version": manifest.version,
        },
        "builder": {"id": builder_id},
    }
    if source_ref:
        provenance["source"] = {"ref": source_ref}
    if signing_secret:
        provenance["signature"] = build_provenance_signature(
            connector=connector,
            provenance=provenance,
            signing_secret=signing_secret,
            signing_key_id=signing_key_id,
        )
    return provenance


def build_provenance_signature(
    *,
    connector: Connector,
    provenance: dict[str, Any],
    signing_secret: str,
    signing_key_id: str,
) -> dict[str, str]:
    """Build an HMAC signature over provenance metadata."""

    if not signing_secret:
        raise ValueError("A non-empty signing_secret is required.")
    manifest = connector.describe()
    unsigned_provenance = json.loads(json.dumps(provenance))
    unsigned_provenance.pop("signature", None)
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        _canonical_json(
            {
                "connector_key": manifest.key,
                "connector_version": manifest.version,
                "provenance": unsigned_provenance,
            }
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "algorithm": "hmac-sha256",
        "key_id": signing_key_id,
        "signed_payload": PROVENANCE_SIGNED_PAYLOAD,
        "signature": signature,
    }


def build_egress_policy(*, allowed_hosts: Iterable[str]) -> dict[str, Any]:
    """Build the default-deny egress policy metadata expected by the registry."""

    hosts = sorted({str(host).strip().lower() for host in allowed_hosts if str(host).strip()})
    if not hosts:
        raise ValueError("At least one allowed host is required.")
    return {
        "version": "1",
        "mode": "provider_proxy",
        "enforcement": "egress_proxy",
        "default_action": "deny",
        "allowed_hosts": hosts,
        "allowed_methods": ["GET"],
        "allowed_ports": [443],
        "allowed_path_prefixes": [],
    }


def write_release_gate_metadata(
    package_dir: str | Path,
    *,
    allowed_hosts: Iterable[str] = (),
    signing_secret: str | None = None,
    signing_key_id: str = "local-author",
    builder_id: str = "orbixal-connector-author-sdk",
    source_ref: str | None = None,
    vulnerability_scanner_name: str = "orbixal-vulnerability-scan",
    malware_scanner_name: str = "orbixal-malware-scan",
    vulnerability_status: str = "passed",
    malware_status: str = "clean",
    vulnerability_findings: Iterable[dict[str, Any]] | None = None,
    malware_findings: Iterable[dict[str, Any]] | None = None,
) -> dict[str, str | None]:
    """Write third-party release-gate metadata and refresh package checksums.

    The package-level signature is regenerated after release-gate files are
    written so the final signature covers scanner attestations, provenance, and
    egress policy metadata.
    """

    package_path = Path(package_dir)
    connector = load_packaged_connector(package_path)
    declared_policy = connector.describe().egress_policy.to_dict()
    supplied_hosts = sorted(
        {str(host).strip().lower().rstrip(".") for host in allowed_hosts if str(host).strip()}
    )
    if supplied_hosts and supplied_hosts != declared_policy["allowed_hosts"]:
        raise ValueError(
            "--allowed-host values must exactly match the connector manifest egress policy."
        )
    resolved_signing_secret = signing_secret or os.getenv(SIGNING_SECRET_ENV)

    paths = {
        "vulnerability_scan_path": package_path / VULNERABILITY_SCAN_FILENAME,
        "malware_scan_path": package_path / MALWARE_SCAN_FILENAME,
        "provenance_path": package_path / PROVENANCE_FILENAME,
        "egress_policy_path": package_path / EGRESS_POLICY_FILENAME,
        "checksums_path": package_path / "checksums.json",
        "signature_path": package_path / SIGNATURE_FILENAME,
    }
    paths["vulnerability_scan_path"].write_text(
        json.dumps(
            build_scan_attestation(
                connector,
                scanner_name=vulnerability_scanner_name,
                status=vulnerability_status,
                findings=vulnerability_findings,
                signing_secret=resolved_signing_secret,
                signing_key_id=signing_key_id,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["malware_scan_path"].write_text(
        json.dumps(
            build_scan_attestation(
                connector,
                scanner_name=malware_scanner_name,
                status=malware_status,
                findings=malware_findings,
                signing_secret=resolved_signing_secret,
                signing_key_id=signing_key_id,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["provenance_path"].write_text(
        json.dumps(
            build_provenance(
                connector,
                builder_id=builder_id,
                source_ref=source_ref,
                signing_secret=resolved_signing_secret,
                signing_key_id=signing_key_id,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["egress_policy_path"].write_text(
        json.dumps(declared_policy, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    checksums = _package_checksums(
        package_path,
        include_signature=False,
    )
    paths["checksums_path"].write_text(
        json.dumps(checksums, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    signature_path: Path | None = None
    if resolved_signing_secret:
        signature_path = paths["signature_path"]
        signature_path.write_text(
            json.dumps(
                build_signature(
                    connector=connector,
                    checksums=checksums,
                    signing_secret=resolved_signing_secret,
                    signing_key_id=signing_key_id,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        checksums["files"][SIGNATURE_FILENAME] = _sha256_hex(signature_path)
        paths["checksums_path"].write_text(
            json.dumps(checksums, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return {
        "package_dir": str(package_path),
        "vulnerability_scan_path": str(paths["vulnerability_scan_path"]),
        "malware_scan_path": str(paths["malware_scan_path"]),
        "provenance_path": str(paths["provenance_path"]),
        "egress_policy_path": str(paths["egress_policy_path"]),
        "checksums_path": str(paths["checksums_path"]),
        "signature_path": str(signature_path) if signature_path else None,
    }


def _signature_payload(
    *,
    connector_key: str,
    connector_version: str,
    checksums: dict[str, Any],
) -> dict[str, Any]:
    return {
        "connector_key": connector_key,
        "connector_version": connector_version,
        "checksums": checksums,
    }


def _package_checksums(package_path: Path, *, include_signature: bool) -> dict[str, Any]:
    filenames = [
        "manifest.json",
        CODE_ARCHIVE_FILENAME,
        "package_metadata.json",
        SBOM_FILENAME,
        VULNERABILITY_SCAN_FILENAME,
        MALWARE_SCAN_FILENAME,
        PROVENANCE_FILENAME,
        EGRESS_POLICY_FILENAME,
    ]
    if include_signature:
        filenames.append(SIGNATURE_FILENAME)
    return {
        "algorithm": "sha256",
        "files": {
            filename: _sha256_hex(package_path / filename)
            for filename in filenames
            if (package_path / filename).is_file()
        },
    }


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _dependency_component(dependency: str) -> dict[str, Any]:
    name = _dependency_name(dependency)
    component: dict[str, Any] = {
        "type": "library",
        "name": name,
        "scope": "required",
        "properties": [
            {
                "name": "orbixal:dependency_expression",
                "value": dependency,
            }
        ],
    }
    version = _dependency_version_hint(dependency)
    if version:
        component["version"] = version
    return component


def _dependency_name(dependency: str) -> str:
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)", dependency)
    if not match:
        raise ValueError(f"Dependency entry has no package name: {dependency}")
    return match.group(1).replace("_", "-").lower()


def _dependency_version_hint(dependency: str) -> str | None:
    for marker in ("==", ">=", "~=", "<=", ">", "<"):
        if marker in dependency:
            return dependency.split(marker, maxsplit=1)[1].split(",", maxsplit=1)[0].strip()
    return None


def resolve_connector_source_paths(
    connector_target: str,
    *,
    source_paths: Iterable[str | Path] | None = None,
) -> list[Path]:
    """Return source paths that should be archived for one connector target."""

    if source_paths is not None:
        paths = [Path(path).resolve() for path in source_paths]
    else:
        paths = discover_connector_source_paths(connector_target)

    if not paths:
        raise ValueError("At least one connector source path is required.")
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Connector source path does not exist: {path}")
        if path.is_symlink():
            raise ValueError(f"Connector source path cannot be a symlink: {path}")
        if not path.is_file() and not path.is_dir():
            raise ValueError(f"Connector source path is not a file or directory: {path}")
    return paths


def discover_connector_source_paths(connector_target: str) -> list[Path]:
    """Infer source paths from a connector target such as ``package.module:Class``."""

    if ":" not in connector_target:
        raise ValueError("Connector target must use the format 'module:Symbol'")

    module_name, _ = connector_target.split(":", 1)
    top_level_module_name = module_name.split(".", 1)[0]
    top_level_module = import_module(top_level_module_name)
    package_paths = getattr(top_level_module, "__path__", None)
    if package_paths:
        return [Path(next(iter(package_paths))).resolve()]

    module = import_module(module_name)
    source_file = inspect.getsourcefile(module)
    if source_file is None:
        raise ValueError(f"Cannot infer source file for connector target '{connector_target}'.")
    return [Path(source_file).resolve()]


def write_code_archive(
    *,
    source_paths: Iterable[str | Path],
    output_path: str | Path,
) -> list[str]:
    """Write a deterministic zip archive containing connector source files."""

    sources = [Path(path).resolve() for path in source_paths]
    files = _collect_archive_files(sources)
    if not files:
        raise ValueError("Connector source paths did not contain packageable files.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_name, source_file in files:
            info = zipfile.ZipInfo(archive_name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source_file.read_bytes())
    return [archive_name for archive_name, _ in files]


def verify_package_checksums(package_dir: str | Path) -> None:
    """Verify bundle files against ``checksums.json``."""

    package_path = Path(package_dir)
    checksums_path = package_path / "checksums.json"
    payload = json.loads(checksums_path.read_text(encoding="utf-8"))
    if payload.get("algorithm") != "sha256":
        raise ValueError("Unsupported package checksum algorithm.")
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Package checksum file is missing file checksums.")

    for relative_path, expected_checksum in files.items():
        if not isinstance(relative_path, str) or not isinstance(expected_checksum, str):
            raise ValueError("Package checksum file contains invalid entries.")
        file_path = package_path / relative_path
        if not file_path.is_file():
            raise FileNotFoundError(f"Package file listed in checksums is missing: {relative_path}")
        actual_checksum = _sha256_hex(file_path)
        if actual_checksum != expected_checksum:
            raise ValueError(f"Package checksum mismatch for {relative_path}.")


def inspect_package_artifact(package_dir: str | Path) -> dict[str, Any]:
    """Return sanitized package metadata and checksum summary for a bundle."""

    package_path = Path(package_dir)
    metadata = json.loads((package_path / "package_metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((package_path / "manifest.json").read_text(encoding="utf-8"))
    checksums = json.loads((package_path / "checksums.json").read_text(encoding="utf-8"))
    files = checksums.get("files") if isinstance(checksums, dict) else None
    return {
        "connector_key": metadata.get("connector_key"),
        "connector_version": metadata.get("connector_version"),
        "connector_target": metadata.get("connector_target"),
        "bundle_format_version": metadata.get("bundle_format_version"),
        "manifest_schema_version": manifest.get("manifest_schema_version"),
        "sdk_version": metadata.get("sdk_version"),
        "runtime_compatibility_range": metadata.get("runtime_compatibility_range"),
        "code_archive": metadata.get("code_archive"),
        "sbom": metadata.get("sbom"),
        "signature": metadata.get("signature"),
        "operations": metadata.get("operations", []),
        "resource_types": metadata.get("resource_types", []),
        "checksums": {
            "algorithm": checksums.get("algorithm") if isinstance(checksums, dict) else None,
            "files": sorted(files) if isinstance(files, dict) else [],
        },
    }


def verify_package_artifact(package_dir: str | Path) -> dict[str, Any]:
    """Verify checksums and entrypoint importability for a package bundle."""

    verify_package_checksums(package_dir)
    connector = load_packaged_connector(package_dir)
    manifest = connector.describe()
    metadata = json.loads((Path(package_dir) / "package_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("connector_key") != manifest.key:
        raise ValueError("Package metadata connector_key does not match connector manifest.")
    if metadata.get("connector_version") != manifest.version:
        raise ValueError("Package metadata connector_version does not match connector manifest.")
    return {
        "valid": True,
        "connector_key": manifest.key,
        "connector_version": manifest.version,
        "connector_target": metadata.get("connector_target"),
    }


def load_packaged_connector(package_dir: str | Path) -> Connector:
    """Load a connector from a packaged bundle directory."""

    package_path = Path(package_dir)
    verify_package_checksums(package_path)
    metadata = json.loads((package_path / "package_metadata.json").read_text(encoding="utf-8"))
    connector_target = metadata.get("connector_target")
    if not isinstance(connector_target, str) or ":" not in connector_target:
        raise ValueError("Package metadata is missing connector_target.")

    code_archive = metadata.get("code_archive")
    if not isinstance(code_archive, dict) or not isinstance(code_archive.get("path"), str):
        raise ValueError("Package metadata is missing code_archive.path.")
    archive_path = package_path / code_archive["path"]
    if not archive_path.is_file():
        raise FileNotFoundError(f"Package code archive was not found: {archive_path}")

    archive_sys_path = str(archive_path)
    if archive_sys_path not in sys.path:
        sys.path.insert(0, archive_sys_path)

    from connector_author_sdk.harness import load_connector

    return load_connector(connector_target)


def _collect_archive_files(source_paths: list[Path]) -> list[tuple[str, Path]]:
    collected: dict[str, Path] = {}
    for source_path in source_paths:
        if source_path.is_file():
            if _should_include_file(source_path):
                _add_archive_file(collected, source_path.name, source_path)
            continue

        archive_root = source_path.parent
        for candidate in sorted(source_path.rglob("*")):
            if candidate.is_symlink():
                raise ValueError(f"Connector package sources cannot contain symlinks: {candidate}")
            if not candidate.is_file() or not _should_include_file(candidate):
                continue
            archive_name = candidate.relative_to(archive_root).as_posix()
            _add_archive_file(collected, archive_name, candidate)

    return sorted(collected.items(), key=lambda item: item[0])


def _add_archive_file(collected: dict[str, Path], archive_name: str, source_file: Path) -> None:
    existing = collected.get(archive_name)
    if existing is not None and existing != source_file:
        raise ValueError(f"Duplicate package archive path: {archive_name}")
    collected[archive_name] = source_file


def _should_include_file(path: Path) -> bool:
    parts = set(path.parts)
    if parts.intersection(EXCLUDED_DIR_NAMES):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return True


__all__ = [
    "BUNDLE_FORMAT_VERSION",
    "CODE_ARCHIVE_FILENAME",
    "EGRESS_POLICY_FILENAME",
    "MALWARE_SCAN_FILENAME",
    "PackageArtifact",
    "PROVENANCE_FILENAME",
    "SCAN_ATTESTATION_SIGNED_PAYLOAD",
    "build_package_metadata",
    "build_egress_policy",
    "build_provenance",
    "build_provenance_signature",
    "build_scan_attestation",
    "build_scan_attestation_signature",
    "build_sbom",
    "build_signature",
    "discover_connector_source_paths",
    "export_manifest",
    "inspect_package_artifact",
    "load_packaged_connector",
    "package_connector",
    "PROVENANCE_SIGNED_PAYLOAD",
    "resolve_connector_source_paths",
    "SIGNING_SECRET_ENV",
    "SIGNATURE_FILENAME",
    "verify_package_artifact",
    "verify_package_checksums",
    "VULNERABILITY_SCAN_FILENAME",
    "write_code_archive",
    "write_release_gate_metadata",
]

"""Packaging helpers for connector authors."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
from importlib import import_module
import inspect
import json
from pathlib import Path
import sys
from typing import Any
import zipfile

from connector_author_sdk.connector import Connector
from connector_author_sdk.validation import validate_manifest, validate_package_metadata


BUNDLE_FORMAT_VERSION = "2"
CODE_ARCHIVE_FILENAME = "connector_code.zip"
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

    def to_dict(self) -> dict[str, str]:
        return {
            "connector_target": self.connector_target,
            "connector_key": self.connector_key,
            "connector_version": self.connector_version,
            "output_dir": self.output_dir,
            "manifest_path": self.manifest_path,
            "metadata_path": self.metadata_path,
            "code_archive_path": self.code_archive_path,
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
    code_archive_filename: str = CODE_ARCHIVE_FILENAME,
    archive_members: Iterable[str] | None = None,
) -> dict[str, Any]:
    manifest = connector.describe()
    return {
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
    source_paths: Iterable[str | Path] | None = None,
) -> PackageArtifact:
    manifest = connector.describe()
    output_path = Path(output_dir) / manifest.key / manifest.version
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
    metadata_path = output_path / "package_metadata.json"
    package_metadata = build_package_metadata(
        connector,
        connector_target=connector_target,
        archive_members=archive_members,
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
    checksums_path = output_path / "checksums.json"
    checksums_path.write_text(
        json.dumps(
            {
                "algorithm": "sha256",
                "files": {
                    "manifest.json": _sha256_hex(manifest_path),
                    CODE_ARCHIVE_FILENAME: _sha256_hex(code_archive_path),
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
        code_archive_path=str(code_archive_path),
        checksums_path=str(checksums_path),
    )


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
    "PackageArtifact",
    "build_package_metadata",
    "discover_connector_source_paths",
    "export_manifest",
    "inspect_package_artifact",
    "load_packaged_connector",
    "package_connector",
    "resolve_connector_source_paths",
    "verify_package_artifact",
    "verify_package_checksums",
    "write_code_archive",
]

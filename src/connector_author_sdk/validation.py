"""Schema validation helpers for connector authors."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from connector_author_sdk.manifests.models import ConnectorManifest
from connector_author_sdk.results.models import ValidationError


PACKAGE_SCHEMA_ROOT = Path(__file__).resolve().parent / "_schemas"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(valid=True)

    @classmethod
    def from_errors(cls, errors: list[ValidationError]) -> "ValidationResult":
        return cls(valid=not errors, errors=errors)


def _schema_path(relative_path: str) -> Path:
    package_path = PACKAGE_SCHEMA_ROOT / relative_path
    if package_path.exists():
        return package_path
    raise FileNotFoundError(f"Bundled schema not found: {relative_path}")


def load_platform_schema(relative_path: str) -> dict[str, Any]:
    return json.loads(_schema_path(relative_path).read_text(encoding="utf-8"))


def validate_json_schema(
    payload: Mapping[str, Any] | dict[str, Any],
    schema: Mapping[str, Any] | dict[str, Any],
) -> ValidationResult:
    validator = Draft202012Validator(schema)
    errors = [
        ValidationError(
            field=".".join(str(part) for part in error.absolute_path) or "$",
            message=error.message,
        )
        for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    ]
    return ValidationResult.from_errors(errors)


def validate_manifest(manifest: ConnectorManifest) -> ValidationResult:
    schema = load_platform_schema("manifest/connector_manifest.schema.json")
    return validate_json_schema(manifest.to_dict(), schema)


def validate_config(
    config: Mapping[str, Any] | dict[str, Any],
    manifest: ConnectorManifest,
) -> ValidationResult:
    return validate_json_schema(config, manifest.config_schema)


def validate_auth_payload(
    auth_payload: Mapping[str, Any] | dict[str, Any],
    manifest: ConnectorManifest,
) -> ValidationResult:
    auth_type = str(manifest.auth_schema.get("type") or "").strip()
    required_fields = [
        field_name
        for field_name in manifest.auth_schema.get("required_fields", [])
        if isinstance(field_name, str) and field_name.strip()
    ]
    optional_fields = [
        field_name
        for field_name in manifest.auth_schema.get("optional_fields", [])
        if isinstance(field_name, str) and field_name.strip()
    ]
    payload = dict(auth_payload)
    errors: list[ValidationError] = []

    if auth_type == "none":
        if payload:
            errors.append(
                ValidationError(
                    field="$",
                    message="Auth payload must be empty when auth_schema.type is 'none'.",
                )
            )
        return ValidationResult.from_errors(errors)

    if not auth_type:
        return ValidationResult.from_errors(
            [ValidationError(field="auth_schema.type", message="Manifest auth_schema.type is required.")]
        )

    for field_name in required_fields:
        value = payload.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(
                ValidationError(
                    field=field_name,
                    message="Missing required auth field.",
                )
            )

    allowed_fields = set(required_fields) | set(optional_fields)
    if auth_type != "custom_headers":
        for field_name in sorted(payload):
            if field_name not in allowed_fields:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message="Unexpected auth field; declare it in auth_schema.required_fields or optional_fields.",
                    )
                )

    return ValidationResult.from_errors(errors)


def validate_records_envelope(
    payload: Mapping[str, Any] | dict[str, Any],
) -> ValidationResult:
    schema = load_platform_schema("results/records_envelope.schema.json")
    return validate_json_schema(payload, schema)


def validate_tabular_envelope(
    payload: Mapping[str, Any] | dict[str, Any],
) -> ValidationResult:
    schema = load_platform_schema("results/tabular_envelope.schema.json")
    return validate_json_schema(payload, schema)


def validate_result_envelope(
    payload: Mapping[str, Any] | dict[str, Any],
) -> ValidationResult:
    kind = payload.get("kind")
    if kind == "records":
        return validate_records_envelope(payload)
    if kind == "tabular":
        return validate_tabular_envelope(payload)
    return ValidationResult.from_errors(
        [
            ValidationError(
                field="kind",
                message="Unsupported result kind. Expected 'records' or 'tabular'.",
            )
        ]
    )

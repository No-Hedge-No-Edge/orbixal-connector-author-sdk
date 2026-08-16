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
PLATFORM_AUTH_TYPES = {
    "none",
    "api_key",
    "oauth2",
    "basic_auth",
    "service_account",
    "custom_headers",
}
SENSITIVE_MANIFEST_KEYS = {"client_secret", "clientSecret"}
BACKEND_MANAGED_OAUTH_KEYS = {
    "callbackUrl",
    "callback_url",
    "clientId",
    "client_id",
    "redirectUri",
    "redirect_uri",
}


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
    base_result = validate_json_schema(manifest.to_dict(), schema)
    errors = [
        *base_result.errors,
        *_validate_manifest_auth_semantics(manifest),
        *_validate_config_schema_contract(manifest.config_schema),
    ]
    return ValidationResult.from_errors(errors)


def validate_package_metadata(
    metadata: Mapping[str, Any] | dict[str, Any],
) -> ValidationResult:
    schema = load_platform_schema("package/package_metadata.schema.json")
    return validate_json_schema(metadata, schema)


def validate_config(
    config: Mapping[str, Any] | dict[str, Any],
    manifest: ConnectorManifest,
) -> ValidationResult:
    return validate_json_schema(config, _closed_config_schema(manifest.config_schema))


def _validate_config_schema_contract(schema: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if schema and schema.get("type") != "object":
        errors.append(
            ValidationError(
                field="config_schema.type",
                message="Connector config schemas must describe an object.",
            )
        )
    for path in _find_schema_keyword(schema, keyword="additionalProperties"):
        errors.append(
            ValidationError(
                field=f"config_schema{path}",
                message=(
                    "additionalProperties is platform-managed and must not be declared. "
                    "Declare accepted configuration keys under properties."
                ),
            )
        )
    return errors


def _find_schema_keyword(value: Any, *, keyword: str, path: str = "") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key == keyword:
                matches.append(item_path)
            matches.extend(_find_schema_keyword(item, keyword=keyword, path=item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            matches.extend(
                _find_schema_keyword(item, keyword=keyword, path=f"{path}[{index}]")
            )
    return matches


def _closed_config_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if not schema:
        return {"type": "object", "properties": {}, "additionalProperties": False}
    closed = _close_object_schemas(schema)
    closed.setdefault("type", "object")
    closed.setdefault("properties", {})
    closed["additionalProperties"] = False
    return closed


def _close_object_schemas(value: Any) -> Any:
    if isinstance(value, dict):
        closed = {key: _close_object_schemas(item) for key, item in value.items()}
        if closed.get("type") == "object" or "properties" in closed:
            closed["additionalProperties"] = False
        return closed
    if isinstance(value, list):
        return [_close_object_schemas(item) for item in value]
    return value


def validate_auth_payload(
    auth_payload: Mapping[str, Any] | dict[str, Any],
    manifest: ConnectorManifest,
) -> ValidationResult:
    if _is_platform_auth_schema(manifest.auth_schema):
        return _validate_platform_auth_payload(auth_payload, manifest.auth_schema)
    return validate_json_schema(auth_payload, manifest.auth_schema)


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


def _validate_manifest_auth_semantics(manifest: ConnectorManifest) -> list[ValidationError]:
    errors = _reject_sensitive_manifest_keys(manifest.to_dict())
    auth_schema = manifest.auth_schema
    if not _is_platform_auth_schema(auth_schema):
        return errors

    auth_type = auth_schema.get("type")
    required_fields = _string_list(auth_schema.get("required_fields", []))
    optional_fields = _string_list(auth_schema.get("optional_fields", []))
    if required_fields is None:
        errors.append(
            ValidationError(
                field="auth_schema.required_fields",
                message="required_fields must be a list of strings.",
            )
        )
    if optional_fields is None:
        errors.append(
            ValidationError(
                field="auth_schema.optional_fields",
                message="optional_fields must be a list of strings.",
            )
        )
    if (
        auth_type == "oauth2"
        and required_fields is not None
        and "access_token" not in required_fields
    ):
        errors.append(
            ValidationError(
                field="auth_schema.required_fields",
                message="oauth2 auth schemas must require access_token.",
            )
        )
    if auth_type == "oauth2":
        errors.extend(_reject_backend_managed_oauth_keys(auth_schema, "auth_schema"))
    return errors


def _validate_platform_auth_payload(
    auth_payload: Mapping[str, Any] | dict[str, Any],
    auth_schema: Mapping[str, Any],
) -> ValidationResult:
    auth_type = auth_schema.get("type")
    if auth_type == "none":
        if auth_payload:
            return ValidationResult.from_errors(
                [
                    ValidationError(
                        field="$",
                        message="Authless connectors must not receive auth payload fields.",
                    )
                ]
            )
        return ValidationResult.ok()

    required_fields = _string_list(auth_schema.get("required_fields", []))
    optional_fields = _string_list(auth_schema.get("optional_fields", []))
    errors: list[ValidationError] = []
    if required_fields is None:
        errors.append(
            ValidationError(
                field="auth_schema.required_fields",
                message="required_fields must be a list of strings.",
            )
        )
        required_fields = []
    if optional_fields is None:
        errors.append(
            ValidationError(
                field="auth_schema.optional_fields",
                message="optional_fields must be a list of strings.",
            )
        )
        optional_fields = []

    allowed_fields = {*required_fields, *optional_fields}
    for field_name in required_fields:
        if field_name not in auth_payload:
            errors.append(
                ValidationError(
                    field=field_name,
                    message=f"'{field_name}' is a required auth field.",
                )
            )
    for field_name in auth_payload:
        if field_name not in allowed_fields:
            errors.append(
                ValidationError(
                    field=field_name,
                    message=f"Unexpected auth field '{field_name}'.",
                )
            )
    return ValidationResult.from_errors(errors)


def _is_platform_auth_schema(auth_schema: Mapping[str, Any] | dict[str, Any]) -> bool:
    return auth_schema.get("type") in PLATFORM_AUTH_TYPES


def _reject_sensitive_manifest_keys(
    payload: Mapping[str, Any],
    path: str = "$",
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for key, value in payload.items():
        field_path = f"{path}.{key}"
        if key in SENSITIVE_MANIFEST_KEYS:
            errors.append(
                ValidationError(
                    field=field_path,
                    message=(
                        "OAuth client secrets must be registered with the backend, "
                        "not embedded in connector manifests."
                    ),
                )
            )
        if isinstance(value, Mapping):
            errors.extend(_reject_sensitive_manifest_keys(value, field_path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    errors.extend(_reject_sensitive_manifest_keys(item, f"{field_path}[{index}]"))
    return errors


def _reject_backend_managed_oauth_keys(
    payload: Mapping[str, Any],
    path: str,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for key, value in payload.items():
        field_path = f"{path}.{key}"
        if key in BACKEND_MANAGED_OAUTH_KEYS:
            errors.append(
                ValidationError(
                    field=field_path,
                    message=(
                        "OAuth app client IDs and callback URLs must be registered "
                        "with the backend, not embedded in connector manifests."
                    ),
                )
            )
        if isinstance(value, Mapping):
            errors.extend(_reject_backend_managed_oauth_keys(value, field_path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    errors.extend(
                        _reject_backend_managed_oauth_keys(item, f"{field_path}[{index}]")
                    )
    return errors


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) and item for item in value):
        return None
    return value

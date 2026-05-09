"""Helpers for constructing connector manifests."""

from __future__ import annotations

from typing import Any

from connector_author_sdk.manifests.models import (
    ConnectorManifest,
    OperationDefinition,
)

_AUTH_TYPE_VALUES = {
    "none",
    "api_key",
    "oauth2",
    "basic_auth",
    "service_account",
    "custom_headers",
}


def oauth2_auth(
    *,
    required_fields: list[str] | None = None,
    optional_fields: list[str] | None = None,
    provider: str | None = None,
    default_scopes: list[str] | None = None,
    authorization_url: str | None = None,
    token_url: str | None = None,
) -> dict[str, Any]:
    """Build a backend-compatible OAuth2 auth schema without app secrets."""

    schema = auth_schema(
        auth_type="oauth2",
        required_fields=required_fields if required_fields is not None else ["access_token"],
        optional_fields=optional_fields
        if optional_fields is not None
        else ["refresh_token", "expires_at", "scopes"],
    )
    if provider is not None:
        schema["provider"] = provider
    if default_scopes is not None:
        schema["default_scopes"] = list(default_scopes)
    if authorization_url is not None:
        schema["authorization_url"] = authorization_url
    if token_url is not None:
        schema["token_url"] = token_url
    return schema


def no_auth() -> dict[str, Any]:
    """Build an auth schema for connectors that need no credentials."""

    return auth_schema(auth_type="none", required_fields=[], optional_fields=[])


def api_key_auth(*, field_name: str = "api_key") -> dict[str, Any]:
    """Build a simple API-key auth schema."""

    return auth_schema(auth_type="api_key", required_fields=[field_name], optional_fields=[])


def auth_schema(
    *,
    auth_type: str,
    required_fields: list[str] | None = None,
    optional_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build the platform auth-schema shape used by backend services."""

    if auth_type not in _AUTH_TYPE_VALUES:
        raise ValueError(f"Unsupported auth_type '{auth_type}'.")
    return {
        "type": auth_type,
        "required_fields": list(required_fields or []),
        "optional_fields": list(optional_fields or []),
    }


def read_operation(
    *,
    name: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any] | None = None,
) -> OperationDefinition:
    return OperationDefinition(
        name=name,
        kind="read",
        input_schema=input_schema,
        output_schema=output_schema,
    )


def query_operation(
    *,
    name: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any] | None = None,
) -> OperationDefinition:
    return OperationDefinition(
        name=name,
        kind="query",
        input_schema=input_schema,
        output_schema=output_schema,
    )


def build_manifest(
    *,
    key: str,
    name: str,
    version: str,
    manifest_schema_version: str,
    sdk_version: str,
    runtime_compatibility_range: str,
    capabilities: list[str],
    auth_schema: dict[str, Any],
    config_schema: dict[str, Any],
    resource_types: list[str],
    operations: list[OperationDefinition],
    entitlement: dict[str, Any] | None = None,
) -> ConnectorManifest:
    return ConnectorManifest(
        key=key,
        name=name,
        version=version,
        manifest_schema_version=manifest_schema_version,
        sdk_version=sdk_version,
        runtime_compatibility_range=runtime_compatibility_range,
        capabilities=capabilities,
        auth_schema=auth_schema,
        entitlement=entitlement,
        config_schema=config_schema,
        resource_types=resource_types,
        operations=operations,
    )

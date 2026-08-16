"""Helpers for constructing connector manifests."""

from __future__ import annotations

from typing import Any

from connector_author_sdk.manifests.models import (
    ConnectorManifest,
    EgressPolicy,
    OperationDefinition,
)

_HTTP_METHODS = frozenset({"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"})


def no_egress() -> EgressPolicy:
    """Declare that connector code requires no external provider access."""

    return EgressPolicy()


def provider_egress(
    *,
    allowed_hosts: list[str],
    allowed_methods: list[str] | None = None,
    allowed_ports: list[int] | None = None,
    allowed_path_prefixes: list[str] | None = None,
) -> EgressPolicy:
    """Declare default-deny provider access enforced by the egress gateway."""

    hosts = sorted({_normalize_host(host) for host in allowed_hosts})
    if not hosts:
        raise ValueError("provider_egress requires at least one allowed host.")
    methods = sorted({method.upper().strip() for method in (allowed_methods or ["GET"])})
    unsupported = set(methods) - _HTTP_METHODS
    if unsupported:
        raise ValueError(f"Unsupported egress methods: {sorted(unsupported)}")
    ports = sorted(set(allowed_ports or [443]))
    if any(port < 1 or port > 65535 for port in ports):
        raise ValueError("Egress ports must be between 1 and 65535.")
    path_prefixes = sorted(set(allowed_path_prefixes or []))
    if any(not prefix.startswith("/") for prefix in path_prefixes):
        raise ValueError("Egress path prefixes must start with '/'.")
    return EgressPolicy(
        mode="provider_proxy",
        allowed_hosts=hosts,
        allowed_methods=methods,
        allowed_ports=ports,
        allowed_path_prefixes=path_prefixes,
    )


def _normalize_host(value: str) -> str:
    host = str(value).strip().lower().rstrip(".")
    if not host or "*" in host or "://" in host or "/" in host:
        raise ValueError(f"Invalid egress host '{value}'.")
    return host

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
    egress_policy: EgressPolicy,
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
        egress_policy=egress_policy,
        entitlement=entitlement,
        config_schema=config_schema,
        resource_types=resource_types,
        operations=operations,
    )

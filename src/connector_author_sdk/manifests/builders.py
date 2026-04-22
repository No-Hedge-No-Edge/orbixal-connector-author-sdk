"""Helpers for constructing connector manifests."""

from __future__ import annotations

from typing import Any

from connector_author_sdk.manifests.models import (
    ConnectorManifest,
    OperationDefinition,
)


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
        config_schema=config_schema,
        resource_types=resource_types,
        operations=operations,
    )

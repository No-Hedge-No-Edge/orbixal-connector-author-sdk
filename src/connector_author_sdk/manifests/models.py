"""Dataclass manifest models for connector authors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from connector_author_sdk.generated.manifest_models import MANIFEST_REQUIRED_FIELDS


OperationKind = Literal["read", "query"]


@dataclass(frozen=True, slots=True)
class OperationDefinition:
    name: str
    kind: OperationKind
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "kind": self.kind,
            "input_schema": self.input_schema,
        }
        if self.output_schema is not None:
            data["output_schema"] = self.output_schema
        return data


@dataclass(frozen=True, slots=True)
class ConnectorManifest:
    key: str
    name: str
    version: str
    manifest_schema_version: str
    sdk_version: str
    runtime_compatibility_range: str
    capabilities: list[str] = field(default_factory=list)
    auth_schema: dict[str, Any] = field(default_factory=dict)
    entitlement: dict[str, Any] | None = None
    config_schema: dict[str, Any] = field(default_factory=dict)
    resource_types: list[str] = field(default_factory=list)
    operations: list[OperationDefinition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "manifest_schema_version": self.manifest_schema_version,
            "sdk_version": self.sdk_version,
            "runtime_compatibility_range": self.runtime_compatibility_range,
            "capabilities": list(self.capabilities),
            "auth_schema": self.auth_schema,
            "entitlement": self.entitlement,
            "config_schema": self.config_schema,
            "resource_types": list(self.resource_types),
            "operations": [operation.to_dict() for operation in self.operations],
        }


__all__ = [
    "ConnectorManifest",
    "MANIFEST_REQUIRED_FIELDS",
    "OperationDefinition",
    "OperationKind",
]

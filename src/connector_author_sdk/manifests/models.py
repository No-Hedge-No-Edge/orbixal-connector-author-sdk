"""Dataclass manifest models for connector authors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from connector_author_sdk.generated.manifest_models import MANIFEST_REQUIRED_FIELDS


OperationKind = Literal["read", "query"]
EgressMode = Literal["none", "provider_proxy"]


@dataclass(frozen=True, slots=True)
class EgressPolicy:
    version: Literal["1"] = "1"
    mode: EgressMode = "none"
    enforcement: Literal["egress_proxy"] = "egress_proxy"
    default_action: Literal["deny"] = "deny"
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_methods: list[str] = field(default_factory=list)
    allowed_ports: list[int] = field(default_factory=list)
    allowed_path_prefixes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "mode": self.mode,
            "enforcement": self.enforcement,
            "default_action": self.default_action,
            "allowed_hosts": list(self.allowed_hosts),
            "allowed_methods": list(self.allowed_methods),
            "allowed_ports": list(self.allowed_ports),
            "allowed_path_prefixes": list(self.allowed_path_prefixes),
        }


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
    egress_policy: EgressPolicy = field(default_factory=EgressPolicy)
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
            "egress_policy": self.egress_policy.to_dict(),
            "entitlement": self.entitlement,
            "config_schema": self.config_schema,
            "resource_types": list(self.resource_types),
            "operations": [operation.to_dict() for operation in self.operations],
        }


__all__ = [
    "ConnectorManifest",
    "EgressMode",
    "EgressPolicy",
    "MANIFEST_REQUIRED_FIELDS",
    "OperationDefinition",
    "OperationKind",
]

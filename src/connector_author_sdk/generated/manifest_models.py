
# Generated from canonical contract schemas. Do not edit by hand.

from typing import Any, Literal, TypedDict


class OperationDefinition(TypedDict, total=False):
    name: str
    kind: Literal['read', 'query']
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class EntitlementDescriptor(TypedDict, total=False):
    provider: str
    requires_byok: bool
    storage_policy: str
    exposure_policy: str
    audit_policy: str
    notes: str


class EgressPolicy(TypedDict):
    version: Literal["1"]
    mode: Literal["none", "provider_proxy"]
    enforcement: Literal["egress_proxy"]
    default_action: Literal["deny"]
    allowed_hosts: list[str]
    allowed_methods: list[str]
    allowed_ports: list[int]
    allowed_path_prefixes: list[str]


class ConnectorManifest(TypedDict):
    key: str
    name: str
    version: str
    manifest_schema_version: str
    sdk_version: str
    runtime_compatibility_range: str
    capabilities: list[str]
    auth_schema: dict[str, Any]
    egress_policy: EgressPolicy
    entitlement: EntitlementDescriptor | None
    config_schema: dict[str, Any]
    resource_types: list[str]
    operations: list[OperationDefinition]


MANIFEST_REQUIRED_FIELDS = ['key', 'name', 'version', 'manifest_schema_version', 'sdk_version', 'runtime_compatibility_range', 'capabilities', 'auth_schema', 'egress_policy', 'config_schema', 'resource_types', 'operations']

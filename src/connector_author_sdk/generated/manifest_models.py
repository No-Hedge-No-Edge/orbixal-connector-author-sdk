
# Generated from canonical contract schemas. Do not edit by hand.

from typing import Any, Literal, TypedDict


class AuthSchemaDescriptor(TypedDict, total=False):
    type: Literal['none', 'api_key', 'oauth2', 'basic_auth', 'service_account', 'custom_headers']
    required_fields: list[str]
    optional_fields: list[str]


class OperationDefinition(TypedDict, total=False):
    name: str
    kind: Literal['read', 'query']
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ConnectorManifest(TypedDict):
    key: str
    name: str
    version: str
    manifest_schema_version: str
    sdk_version: str
    runtime_compatibility_range: str
    capabilities: list[str]
    auth_schema: AuthSchemaDescriptor
    config_schema: dict[str, Any]
    resource_types: list[str]
    operations: list[OperationDefinition]


MANIFEST_REQUIRED_FIELDS = ['key', 'name', 'version', 'manifest_schema_version', 'sdk_version', 'runtime_compatibility_range', 'capabilities', 'auth_schema', 'config_schema', 'resource_types', 'operations']

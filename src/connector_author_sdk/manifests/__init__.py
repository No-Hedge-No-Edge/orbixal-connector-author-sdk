"""Manifest models and helpers for connector authors."""

from connector_author_sdk.manifests.builders import (
    api_key_auth,
    auth_schema,
    build_manifest,
    no_auth,
    oauth2_auth,
    query_operation,
    read_operation,
)
from connector_author_sdk.manifests.models import (
    ConnectorManifest,
    MANIFEST_REQUIRED_FIELDS,
    OperationDefinition,
    OperationKind,
)

__all__ = [
    "ConnectorManifest",
    "MANIFEST_REQUIRED_FIELDS",
    "OperationDefinition",
    "OperationKind",
    "api_key_auth",
    "auth_schema",
    "build_manifest",
    "no_auth",
    "oauth2_auth",
    "query_operation",
    "read_operation",
]

"""Local execution harness for connector authors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from inspect import isclass
from typing import Any

from connector_author_sdk.connector import Connector
from connector_author_sdk.context import AuthContext, ConnectorContext
from connector_author_sdk.http import SimpleHttpClient
from connector_author_sdk.results import (
    ConnectorResult,
    QueryRequest,
    ReadRequest,
    RecordsResult,
    ResourcePage,
    ResultMeta,
    TabularResult,
)
from connector_author_sdk.validation import (
    ValidationResult,
    validate_auth_payload,
    validate_config,
    validate_manifest,
    validate_result_envelope,
)


def _ensure_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _validation_to_dict(result: ValidationResult) -> dict[str, Any]:
    return {
        "valid": result.valid,
        "errors": [
            {"field": error.field, "message": error.message} for error in result.errors
        ],
    }


def _normalize_connector_result(
    value: ConnectorResult | RecordsResult | TabularResult,
    *,
    meta: ResultMeta,
) -> ConnectorResult:
    if isinstance(value, ConnectorResult):
        return ConnectorResult(
            kind=value.kind,
            payload=dict(value.payload),
            meta=meta,
            cursor=value.cursor,
            raw=value.raw,
        )
    if isinstance(value, RecordsResult):
        return value.to_connector_result(meta=meta)
    if isinstance(value, TabularResult):
        return value.to_connector_result(meta=meta)
    raise TypeError(f"Unsupported connector result type: {type(value)!r}")


def _result_meta(ctx: ConnectorContext, action: str, entitlement: dict[str, Any] | None = None) -> ResultMeta:
    return ResultMeta(
        connector_key=ctx.connector_key,
        connector_version=ctx.connector_version,
        action=action,
        request_id=ctx.execution_id,
        entitlement=entitlement,
    )


def _validated_result_payload(
    value: ConnectorResult | RecordsResult | TabularResult,
    *,
    meta: ResultMeta,
) -> dict[str, Any]:
    payload = _normalize_connector_result(value, meta=meta).to_dict()
    validation = validate_result_envelope(payload)
    if not validation.valid:
        raise ValueError(
            "Normalized connector result does not match the canonical schema: "
            f"{validation.errors!r}"
        )
    return payload


@dataclass(frozen=True, slots=True)
class ValidationReport:
    manifest: ValidationResult
    config_schema: ValidationResult
    config_semantic: ValidationResult
    auth: ValidationResult

    @property
    def valid(self) -> bool:
        return (
            self.manifest.valid
            and self.config_schema.valid
            and self.config_semantic.valid
            and self.auth.valid
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "manifest": _validation_to_dict(self.manifest),
            "config_schema": _validation_to_dict(self.config_schema),
            "config_semantic": _validation_to_dict(self.config_semantic),
            "auth": _validation_to_dict(self.auth),
        }


def load_connector(target: str) -> Connector:
    """Load a connector from ``module:Symbol``."""

    if ":" not in target:
        raise ValueError("Connector target must use the format 'module:Symbol'")

    module_name, symbol_name = target.split(":", 1)
    module = import_module(module_name)
    symbol = getattr(module, symbol_name)

    if isinstance(symbol, Connector):
        return symbol

    if isclass(symbol) and issubclass(symbol, Connector):
        return symbol()

    if callable(symbol):
        instance = symbol()
        if isinstance(instance, Connector):
            return instance

    raise TypeError(f"Loaded symbol is not a Connector: {target}")


def build_context(
    connector: Connector,
    *,
    config: Mapping[str, Any] | None = None,
    auth_payload: Mapping[str, Any] | None = None,
    auth_type: str | None = None,
    instance_id: str = "local-instance",
    owner_type: str = "user",
    owner_id: str = "local-user",
    execution_id: str = "local-execution",
    http: Any | None = None,
    platform_http: Any | None = None,
    project_id: str | None = None,
) -> ConnectorContext:
    manifest = connector.describe()
    resolved_auth_payload = _ensure_mapping(auth_payload)
    manifest_auth_type = str(manifest.auth_schema.get("type") or "").strip() or "none"
    return ConnectorContext(
        instance_id=instance_id,
        connector_key=manifest.key,
        connector_version=manifest.version,
        owner_type=owner_type,
        owner_id=owner_id,
        config=_ensure_mapping(config),
        auth=AuthContext(
            auth_type=auth_type or manifest_auth_type,
            values=resolved_auth_payload,
        ),
        http=http or SimpleHttpClient(),
        platform_http=platform_http,
        project_id=project_id,
        execution_id=execution_id,
    )


def validate_connector(
    connector: Connector,
    *,
    config: Mapping[str, Any] | None = None,
    auth_payload: Mapping[str, Any] | None = None,
) -> ValidationReport:
    manifest = connector.describe()
    resolved_config = _ensure_mapping(config)
    resolved_auth = _ensure_mapping(auth_payload)
    return ValidationReport(
        manifest=validate_manifest(manifest),
        config_schema=validate_config(resolved_config, manifest),
        config_semantic=connector.validate_config(resolved_config),
        auth=validate_auth_payload(resolved_auth, manifest),
    )


def describe_connector(connector: Connector) -> dict[str, Any]:
    return connector.describe().to_dict()


def run_test_connection(
    connector: Connector,
    *,
    config: Mapping[str, Any] | None = None,
    auth_payload: Mapping[str, Any] | None = None,
    auth_type: str | None = None,
    instance_id: str = "local-instance",
    owner_type: str = "user",
    owner_id: str = "local-user",
    execution_id: str = "local-execution",
) -> dict[str, Any]:
    ctx = build_context(
        connector,
        config=config,
        auth_payload=auth_payload,
        auth_type=auth_type,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
    )
    result = connector.test_connection(ctx)
    return {
        "success": result.success,
        "summary": result.summary,
        "error_code": result.error_code,
        "details": result.details,
    }


def run_list_resources(
    connector: Connector,
    *,
    config: Mapping[str, Any] | None = None,
    auth_payload: Mapping[str, Any] | None = None,
    auth_type: str | None = None,
    query: Mapping[str, Any] | None = None,
    instance_id: str = "local-instance",
    owner_type: str = "user",
    owner_id: str = "local-user",
    execution_id: str = "local-execution",
) -> dict[str, Any]:
    ctx = build_context(
        connector,
        config=config,
        auth_payload=auth_payload,
        auth_type=auth_type,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
    )
    page: ResourcePage = connector.list_resources(ctx, query=query)
    return {
        "items": [
            {
                "id": item.id,
                "type": item.type,
                "name": item.name,
                "attributes": dict(item.attributes),
            }
            for item in page.items
        ],
        "cursor": page.cursor,
    }


def run_read(
    connector: Connector,
    *,
    action: str,
    params: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    auth_payload: Mapping[str, Any] | None = None,
    auth_type: str | None = None,
    include_raw: bool = False,
    instance_id: str = "local-instance",
    owner_type: str = "user",
    owner_id: str = "local-user",
    execution_id: str = "local-execution",
) -> dict[str, Any]:
    manifest = connector.describe()
    ctx = build_context(
        connector,
        config=config,
        auth_payload=auth_payload,
        auth_type=auth_type,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
    )
    result = connector.read(
        ctx,
        ReadRequest(
            action=action,
            params=_ensure_mapping(params),
            include_raw=include_raw,
        ),
    )
    return _validated_result_payload(
        result,
        meta=_result_meta(ctx, action, entitlement=manifest.entitlement),
    )


def run_query(
    connector: Connector,
    *,
    action: str,
    params: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    auth_payload: Mapping[str, Any] | None = None,
    auth_type: str | None = None,
    cursor: str | None = None,
    include_raw: bool = False,
    instance_id: str = "local-instance",
    owner_type: str = "user",
    owner_id: str = "local-user",
    execution_id: str = "local-execution",
) -> dict[str, Any]:
    manifest = connector.describe()
    ctx = build_context(
        connector,
        config=config,
        auth_payload=auth_payload,
        auth_type=auth_type,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
    )
    result = connector.query(
        ctx,
        QueryRequest(
            action=action,
            params=_ensure_mapping(params),
            cursor=cursor,
            include_raw=include_raw,
        ),
    )
    return _validated_result_payload(
        result,
        meta=_result_meta(ctx, action, entitlement=manifest.entitlement),
    )


__all__ = [
    "ValidationReport",
    "build_context",
    "describe_connector",
    "load_connector",
    "run_list_resources",
    "run_query",
    "run_read",
    "run_test_connection",
    "validate_connector",
]

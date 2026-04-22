# Generated from canonical contract schemas. Do not edit by hand.

from typing import Any, Literal, TypedDict


class EntitlementDescriptor(TypedDict, total=False):
    provider: str
    requires_byok: bool
    storage_policy: str
    exposure_policy: str
    audit_policy: str
    notes: str


class RecordItem(TypedDict, total=False):
    id: str
    type: str
    title: str | None
    content: dict[str, Any]
    attributes: dict[str, Any]
    timestamps: dict[str, Any]
    source: dict[str, Any]


class RecordsMeta(TypedDict):
    connector_key: str
    connector_version: str
    action: str
    request_id: str
    entitlement: EntitlementDescriptor | None


class RecordsEnvelope(TypedDict, total=False):
    kind: Literal['records']
    records: list[RecordItem]
    cursor: str | None
    meta: RecordsMeta
    raw: dict[str, Any]


class ColumnDef(TypedDict):
    name: str
    type: str


class RowItem(TypedDict):
    row_id: str
    values: dict[str, Any]


class TabularMeta(TypedDict):
    connector_key: str
    connector_version: str
    action: str
    request_id: str
    entitlement: EntitlementDescriptor | None


class TabularEnvelope(TypedDict, total=False):
    kind: Literal['tabular']
    columns: list[ColumnDef]
    rows: list[RowItem]
    cursor: str | None
    meta: TabularMeta
    raw: dict[str, Any]


ENTITLEMENT_REQUIRED_FIELDS = ['exposure_policy', 'provider', 'requires_byok', 'storage_policy']

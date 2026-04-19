
# Generated from canonical contract schemas. Do not edit by hand.

from typing import Any, Literal, TypedDict


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


class TabularEnvelope(TypedDict, total=False):
    kind: Literal['tabular']
    columns: list[ColumnDef]
    rows: list[RowItem]
    cursor: str | None
    meta: TabularMeta
    raw: dict[str, Any]

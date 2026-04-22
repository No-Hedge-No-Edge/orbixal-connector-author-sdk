"""Dataclass request/result models for connector authors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationError:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    success: bool
    summary: str
    error_code: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ResourceItem:
    id: str
    type: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResourcePage:
    items: list[ResourceItem]
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class ReadRequest:
    action: str
    params: dict[str, Any]
    include_raw: bool = False


@dataclass(frozen=True, slots=True)
class QueryRequest:
    action: str
    params: dict[str, Any]
    cursor: str | None = None
    include_raw: bool = False


@dataclass(frozen=True, slots=True)
class ColumnDef:
    name: str
    type: str


@dataclass(frozen=True, slots=True)
class RecordItem:
    id: str
    type: str
    title: str | None = None
    content: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    timestamps: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RowItem:
    row_id: str
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ResultMeta:
    connector_key: str
    connector_version: str
    action: str
    request_id: str
    entitlement: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConnectorResult:
    kind: str
    payload: dict[str, Any]
    meta: ResultMeta | None = None
    cursor: str | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {"kind": self.kind, **self.payload, "cursor": self.cursor}
        if self.meta is not None:
            data["meta"] = asdict(self.meta)
        if self.raw is not None:
            data["raw"] = self.raw
        return data


@dataclass(frozen=True, slots=True)
class RecordsResult:
    records: list[RecordItem]
    cursor: str | None = None
    raw: dict[str, Any] | None = None

    def to_connector_result(self, meta: ResultMeta | None = None) -> ConnectorResult:
        return ConnectorResult(
            kind="records",
            payload={"records": [asdict(record) for record in self.records]},
            meta=meta,
            cursor=self.cursor,
            raw=self.raw,
        )


@dataclass(frozen=True, slots=True)
class TabularResult:
    columns: list[ColumnDef]
    rows: list[RowItem]
    cursor: str | None = None
    raw: dict[str, Any] | None = None

    def to_connector_result(self, meta: ResultMeta | None = None) -> ConnectorResult:
        return ConnectorResult(
            kind="tabular",
            payload={
                "columns": [asdict(column) for column in self.columns],
                "rows": [asdict(row) for row in self.rows],
            },
            meta=meta,
            cursor=self.cursor,
            raw=self.raw,
        )


__all__ = [
    "ColumnDef",
    "ConnectionTestResult",
    "ConnectorResult",
    "QueryRequest",
    "ReadRequest",
    "RecordItem",
    "RecordsResult",
    "ResultMeta",
    "ResourceItem",
    "ResourcePage",
    "RowItem",
    "TabularResult",
    "ValidationError",
]

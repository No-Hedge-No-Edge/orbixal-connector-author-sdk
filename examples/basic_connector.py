from typing import Any, Mapping

from connector_author_sdk import (
    ColumnDef,
    ConnectionTestResult,
    Connector,
    ConnectorContext,
    QueryRequest,
    ReadRequest,
    RecordItem,
    RecordsResult,
    ResourceItem,
    ResourcePage,
    RowItem,
    TabularResult,
    ValidationError,
    ValidationResult,
    build_manifest,
    query_operation,
    read_operation,
)


class ExampleConnector(Connector):
    def describe(self):
        return build_manifest(
            key="example",
            name="Example Connector",
            version="0.1.1",
            manifest_schema_version="2026-01",
            sdk_version="0.1.1",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get", "search", "resource_list"],
            auth_schema={
                "type": "oauth2",
                "required_fields": ["access_token"],
            },
            config_schema={
                "type": "object",
                "properties": {"workspace": {"type": "string"}},
                "required": ["workspace"],
            },
            resource_types=["item"],
            operations=[
                read_operation(
                    name="get_item",
                    input_schema={
                        "type": "object",
                        "properties": {"id": {"type": "integer"}},
                        "required": ["id"],
                    },
                ),
                query_operation(
                    name="search_items",
                    input_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                ),
            ],
        )

    def validate_config(self, config: Mapping[str, Any]) -> ValidationResult:
        if config.get("workspace") == "forbidden":
            return ValidationResult.from_errors(
                [ValidationError(field="workspace", message="workspace is forbidden")]
            )
        return ValidationResult.ok()

    def test_connection(self, ctx: ConnectorContext) -> ConnectionTestResult:
        if ctx.auth.get("access_token"):
            return ConnectionTestResult(success=True, summary="connected")
        return ConnectionTestResult(
            success=False,
            summary="missing token",
            error_code="missing_token",
        )

    def list_resources(
        self,
        ctx: ConnectorContext,
        query: Mapping[str, Any] | None = None,
    ) -> ResourcePage:
        return ResourcePage(
            items=[
                ResourceItem(
                    id="item",
                    type="resource_type",
                    name="Item",
                    attributes={"workspace": ctx.config.get("workspace")},
                )
            ]
        )

    def read(self, ctx: ConnectorContext, request: ReadRequest):
        return RecordsResult(
            records=[
                RecordItem(
                    id=str(request.params["id"]),
                    type="item",
                    title="Example Item",
                    attributes={"workspace": ctx.config.get("workspace")},
                )
            ]
        )

    def query(self, ctx: ConnectorContext, request: QueryRequest):
        return TabularResult(
            columns=[ColumnDef(name="query", type="string")],
            rows=[RowItem(row_id="1", values={"query": request.params["query"]})],
        )

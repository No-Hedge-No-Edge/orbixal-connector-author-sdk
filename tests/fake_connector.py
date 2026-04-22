from typing import Any, Mapping

from connector_author_sdk.connector import Connector
from connector_author_sdk.context import ConnectorContext
from connector_author_sdk.manifests import build_manifest, query_operation, read_operation
from connector_author_sdk.results import (
    ColumnDef,
    ConnectionTestResult,
    QueryRequest,
    ReadRequest,
    RecordItem,
    RecordsResult,
    ResourceItem,
    ResourcePage,
    RowItem,
    TabularResult,
    ValidationError,
)
from connector_author_sdk.validation import ValidationResult


class FakeConnector(Connector):
    def describe(self):
        return build_manifest(
            key="fake",
            name="Fake",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
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
            resource_types=["issue"],
            operations=[
                read_operation(
                    name="get_issue",
                    input_schema={
                        "type": "object",
                        "properties": {"issue_number": {"type": "integer"}},
                        "required": ["issue_number"],
                    },
                ),
                query_operation(
                    name="search_issues",
                    input_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                ),
            ],
        )

    def validate_config(self, config: Mapping[str, Any]) -> ValidationResult:
        if config.get("workspace") == "invalid":
            return ValidationResult.from_errors(
                [ValidationError(field="workspace", message="workspace is invalid")]
            )
        return ValidationResult.ok()

    def test_connection(self, ctx: ConnectorContext) -> ConnectionTestResult:
        if ctx.auth.get("access_token"):
            return ConnectionTestResult(success=True, summary="ok")
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
                    id="issue",
                    type="resource_type",
                    name="Issue",
                    attributes={"workspace": ctx.config.get("workspace")},
                )
            ]
        )

    def read(self, ctx: ConnectorContext, request: ReadRequest):
        return RecordsResult(
            records=[
                RecordItem(
                    id=str(request.params["issue_number"]),
                    type="issue",
                    title="Loaded",
                    attributes={"workspace": ctx.config.get("workspace")},
                )
            ],
            raw={"action": request.action} if request.include_raw else None,
        )

    def query(self, ctx: ConnectorContext, request: QueryRequest):
        return TabularResult(
            columns=[ColumnDef(name="query", type="string")],
            rows=[RowItem(row_id="1", values={"query": request.params["query"]})],
            cursor="next-page",
            raw={"cursor": request.cursor} if request.include_raw else None,
        )

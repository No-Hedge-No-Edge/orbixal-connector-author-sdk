import sys
from pathlib import Path
import unittest

from connector_author_sdk.connector import Connector
from connector_author_sdk.context import ConnectorContext
from connector_author_sdk.harness import run_query, run_read
from connector_author_sdk.manifests import build_manifest, query_operation, read_operation
from connector_author_sdk.results import (
    ColumnDef,
    ConnectionTestResult,
    ConnectorResult,
    QueryRequest,
    ReadRequest,
    ResourcePage,
    RowItem,
    TabularResult,
)
from connector_author_sdk.validation import (
    ValidationResult,
    validate_records_envelope,
    validate_result_envelope,
    validate_tabular_envelope,
)


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


class BrokenConnector(Connector):
    def describe(self):
        return build_manifest(
            key="broken",
            name="Broken",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get", "search"],
            auth_schema={"type": "none"},
            config_schema={"type": "object"},
            resource_types=["item"],
            operations=[
                read_operation(name="get_item", input_schema={"type": "object"}),
                query_operation(name="search_items", input_schema={"type": "object"}),
            ],
        )

    def validate_config(self, config):
        return ValidationResult.ok()

    def test_connection(self, ctx: ConnectorContext):
        return ConnectionTestResult(success=True, summary="ok")

    def list_resources(self, ctx: ConnectorContext, query=None):
        return ResourcePage(items=[])

    def read(self, ctx: ConnectorContext, request: ReadRequest):
        return ConnectorResult(
            kind="records",
            payload={"records": [{"type": "item"}]},
            cursor=None,
        )

    def query(self, ctx: ConnectorContext, request: QueryRequest):
        return TabularResult(
            columns=[ColumnDef(name="q", type="string")],
            rows=[RowItem(row_id="1", values={"q": request.params.get("query", "")})],
        )


class ResultValidationTests(unittest.TestCase):
    def test_validate_records_envelope(self) -> None:
        result = validate_records_envelope(
            {
                "kind": "records",
                "records": [{"id": "1", "type": "item"}],
                "cursor": None,
                "meta": {
                    "connector_key": "fake",
                    "connector_version": "1.0.0",
                    "action": "get_item",
                    "request_id": "req_1",
                },
            }
        )
        self.assertTrue(result.valid)

    def test_validate_tabular_envelope(self) -> None:
        result = validate_tabular_envelope(
            {
                "kind": "tabular",
                "columns": [{"name": "q", "type": "string"}],
                "rows": [{"row_id": "1", "values": {"q": "bug"}}],
                "cursor": None,
                "meta": {
                    "connector_key": "fake",
                    "connector_version": "1.0.0",
                    "action": "search_items",
                    "request_id": "req_2",
                },
            }
        )
        self.assertTrue(result.valid)

    def test_validate_result_envelope_rejects_unknown_kind(self) -> None:
        result = validate_result_envelope({"kind": "weird"})
        self.assertFalse(result.valid)
        self.assertEqual(result.errors[0].field, "kind")

    def test_harness_rejects_invalid_records_result(self) -> None:
        with self.assertRaises(ValueError):
            run_read(
                BrokenConnector(),
                action="get_item",
                params={},
                config={},
                auth_payload={},
            )

    def test_harness_accepts_valid_tabular_result(self) -> None:
        result = run_query(
            BrokenConnector(),
            action="search_items",
            params={"query": "bug"},
            config={},
            auth_payload={},
        )
        self.assertEqual(result["meta"]["action"], "search_items")

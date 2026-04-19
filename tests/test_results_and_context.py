import unittest

from connector_author_sdk.context import AuthContext, ConnectorContext
from connector_author_sdk.results import (
    ColumnDef,
    QueryRequest,
    RecordItem,
    RecordsResult,
    ResultMeta,
    RowItem,
    TabularResult,
)

class ResultsAndContextTests(unittest.TestCase):
    def test_auth_context_get(self) -> None:
        auth = AuthContext(auth_type="oauth2", values={"access_token": "token"})
        self.assertEqual(auth.get("access_token"), "token")
        self.assertEqual(auth.get("missing", "fallback"), "fallback")

    def test_connector_context_defaults(self) -> None:
        ctx = ConnectorContext(
            instance_id="conninst_1",
            connector_key="github",
            connector_version="1.0.0",
            owner_type="org",
            owner_id="org_1",
        )
        self.assertEqual(ctx.config, {})
        self.assertEqual(ctx.auth.auth_type, "none")

    def test_records_result_converts_to_connector_result(self) -> None:
        result = RecordsResult(
            records=[RecordItem(id="1", type="issue", title="Bug")],
            cursor="next",
        ).to_connector_result(
            meta=ResultMeta(
                connector_key="github",
                connector_version="1.0.0",
                action="get_issue",
                request_id="req_1",
            )
        )
        self.assertEqual(result.kind, "records")
        self.assertEqual(result.payload["records"][0]["id"], "1")
        self.assertEqual(result.cursor, "next")
        self.assertEqual(result.to_dict()["meta"]["action"], "get_issue")

    def test_tabular_result_converts_to_connector_result(self) -> None:
        result = TabularResult(
            columns=[ColumnDef(name="symbol", type="string")],
            rows=[RowItem(row_id="1", values={"symbol": "AAPL"})],
        ).to_connector_result(
            meta=ResultMeta(
                connector_key="stocks",
                connector_version="1.0.0",
                action="search_prices",
                request_id="req_2",
            )
        )
        self.assertEqual(result.kind, "tabular")
        self.assertEqual(result.payload["rows"][0]["row_id"], "1")
        self.assertEqual(result.to_dict()["meta"]["connector_key"], "stocks")

    def test_query_request_holds_action_and_params(self) -> None:
        request = QueryRequest(action="search_issues", params={"query": "bug"})
        self.assertEqual(request.action, "search_issues")
        self.assertEqual(request.params["query"], "bug")

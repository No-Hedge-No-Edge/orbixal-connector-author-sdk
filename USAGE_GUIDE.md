# Connector Author SDK Usage Guide

This guide shows how to build and run a connector with the Orbixal Author SDK.

It covers:
- local setup
- scaffolding a new connector
- implementing the connector class
- validating config and auth
- running `describe`, `test_connection`, `list_resources`, `read`, and `query`
- packaging a connector bundle
- the main SDK types and helpers

## 1. Install the SDK Locally

From the SDK repo root:

```bash
uv lock
uv sync
```

Run the SDK tests:

```bash
uv run python -m unittest discover tests
```

## 2. Scaffold a New Connector

Generate a starter connector package:

```bash
uv run orbixal-connector init \
  --connector-key github_internal \
  --output-dir ./tmp/github_internal
```

This creates:

```text
tmp/github_internal/
  README.md
  pyproject.toml
  src/
    orbixal_connector_github_internal/
      __init__.py
      connector.py
  tests/
    test_connector.py
```

The scaffold command lives in `src/connector_author_sdk/scaffold.py`.

## 3. Implement the Connector Class

Every connector implements the base interface from `src/connector_author_sdk/connector.py`.

```python
from connector_author_sdk import Connector

class MyConnector(Connector):
    def describe(self): ...
    def validate_config(self, config): ...
    def test_connection(self, ctx): ...
    def list_resources(self, ctx, query=None): ...
    def read(self, ctx, request): ...
    def query(self, ctx, request): ...
```

The smallest working reference is the example connector in `examples/basic_connector.py`.

## 4. Define the Manifest

Use `build_manifest`, `read_operation`, `query_operation`, and auth helpers from
`src/connector_author_sdk/manifests/builders.py`.

Example:

```python
from connector_author_sdk import build_manifest, oauth2_auth, read_operation, query_operation

def describe(self):
    return build_manifest(
        key="github_internal",
        name="GitHub Internal",
        version="0.1.1",
        manifest_schema_version="2026-01",
        sdk_version="0.1.1",
        runtime_compatibility_range=">=1.0,<2.0",
        capabilities=["record_get", "search", "resource_list"],
        auth_schema=oauth2_auth(provider="github", default_scopes=["repo", "read:user"]),
        config_schema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string"}
            },
            "required": ["workspace"],
        },
        resource_types=["repository", "issue"],
        operations=[
            read_operation(
                name="get_issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "issue_number": {"type": "integer"},
                    },
                    "required": ["repo", "issue_number"],
                },
            ),
            query_operation(
                name="search_issues",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            ),
        ],
    )
```

Canonical manifest validation is provided by `src/connector_author_sdk/validation.py`.

OAuth helpers only declare the resolved auth fields a connector needs. OAuth app credentials
such as `client_secret`, callback URLs, authorization sessions, code exchange, token storage,
refresh, and revocation are backend-owned.

## 5. Validate Config Semantics

`config_schema` handles shape validation. `validate_config()` is where connector-specific rules go.

Example:

```python
from connector_author_sdk import ValidationError, ValidationResult

def validate_config(self, config):
    if config.get("workspace") == "forbidden":
        return ValidationResult.from_errors(
            [ValidationError(field="workspace", message="workspace is forbidden")]
        )
    return ValidationResult.ok()
```

The local harness combines:
- manifest validation
- config schema validation
- semantic config validation
- auth payload validation

## 6. Use the Runtime Context

Connectors receive `ConnectorContext` from `src/connector_author_sdk/context.py`.

Important fields:
- `ctx.config`
- `ctx.auth`
- `ctx.execution_id`
- `ctx.connector_key`
- `ctx.connector_version`
- `ctx.http`

Example:

```python
def test_connection(self, ctx):
    token = ctx.auth.get("access_token")
    if not token:
        ...
```

For OAuth connectors, `ctx.auth` contains backend-resolved runtime auth. Connector code should
read values such as `access_token`; it should not start OAuth, exchange authorization codes,
store refresh tokens, or know the OAuth app `client_secret`.

For local runs, the harness injects a default HTTP client from `src/connector_author_sdk/http.py`.

## 7. Return Records and Tabular Results

Use the result types from `src/connector_author_sdk/results/models.py`.

### Records example

```python
from connector_author_sdk import RecordItem, RecordsResult

def read(self, ctx, request):
    return RecordsResult(
        records=[
            RecordItem(
                id="42",
                type="issue",
                title="Bug",
                attributes={"repo": "orbixal/api"},
            )
        ]
    )
```

### Tabular example

```python
from connector_author_sdk import ColumnDef, RowItem, TabularResult

def query(self, ctx, request):
    return TabularResult(
        columns=[ColumnDef(name="symbol", type="string")],
        rows=[RowItem(row_id="1", values={"symbol": "AAPL"})],
    )
```

The local harness automatically normalizes these into the canonical runtime envelope and injects `meta`:
- `connector_key`
- `connector_version`
- `action`
- `request_id`

It also validates the final envelope against the bundled schemas before returning it.

## 8. Run the Connector Locally

All CLI commands are implemented in `src/connector_author_sdk/cli.py`.

Assume your connector class is importable as `my_connector.connector:MyConnector`.

### Describe

```bash
uv run orbixal-connector describe \
  --connector my_connector.connector:MyConnector
```

### Validate

```bash
uv run orbixal-connector validate \
  --connector my_connector.connector:MyConnector \
  --config '{"workspace":"demo"}' \
  --auth '{"access_token":"token"}'
```

You can also pass file paths by prefixing with `@`:

```bash
uv run orbixal-connector validate \
  --connector my_connector.connector:MyConnector \
  --config @./config.json \
  --auth @./auth.json
```

### Test Connection

```bash
uv run orbixal-connector test-connection \
  --connector my_connector.connector:MyConnector \
  --config '{"workspace":"demo"}' \
  --auth '{"access_token":"token"}'
```

### List Resources

```bash
uv run orbixal-connector list-resources \
  --connector my_connector.connector:MyConnector \
  --config '{"workspace":"demo"}' \
  --auth '{"access_token":"token"}'
```

### Run Read

```bash
uv run orbixal-connector run read \
  --connector my_connector.connector:MyConnector \
  --action get_issue \
  --params '{"repo":"orbixal/api","issue_number":42}' \
  --config '{"workspace":"demo"}' \
  --auth '{"access_token":"token"}'
```

### Run Query

```bash
uv run orbixal-connector run query \
  --connector my_connector.connector:MyConnector \
  --action search_issues \
  --params '{"query":"label:bug"}' \
  --config '{"workspace":"demo"}' \
  --auth '{"access_token":"token"}'
```

## 9. Understand the Local Output Shape

`read` and `query` return canonical runtime-style envelopes.

Example `records` output:

```json
{
  "kind": "records",
  "records": [
    {
      "id": "42",
      "type": "issue",
      "title": "Bug",
      "content": {},
      "attributes": {
        "repo": "orbixal/api"
      },
      "timestamps": {},
      "source": {}
    }
  ],
  "cursor": null,
  "meta": {
    "connector_key": "github_internal",
    "connector_version": "0.1.0",
    "action": "get_issue",
    "request_id": "local-execution"
  }
}
```

That matters because local output now matches what runtime expects.

## 10. Raise Structured Errors

The SDK exposes sanitized exception types in `src/connector_author_sdk/errors.py`:
- `AuthInvalidError`
- `AuthExpiredError`
- `ProviderTimeoutError`
- `ProviderRateLimitedError`
- `ResourceNotFoundError`
- `InvalidRequestError`
- `MisconfigurationError`
- `ProviderUnavailableError`

Example:

```python
from connector_author_sdk import AuthInvalidError

def test_connection(self, ctx):
    if not ctx.auth.get("access_token"):
        raise AuthInvalidError(provider="github")
```

The CLI catches SDK exceptions and emits structured JSON errors to stderr.

## 11. Use the Default HTTP Client

For local development, `ctx.http` is a `SimpleHttpClient`.

Example:

```python
def test_connection(self, ctx):
    response = ctx.http.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {ctx.auth.get('access_token')}"},
        timeout=10,
    )
    if response.status_code == 401:
        ...
```

The SDK’s local client is intentionally small. Runtime can later inject a richer implementation with tracing, redaction, retries, and policy enforcement.

## 12. Package the Connector

Generate a publication bundle:

```bash
uv run orbixal-connector package \
  --connector my_connector.connector:MyConnector \
  --output-dir ./dist/connectors
```

Current bundle layout:

```text
dist/connectors/
  <connector_key>/
    <connector_version>/
      manifest.json
      package_metadata.json
      checksums.json
```

Packaging helpers live in `src/connector_author_sdk/packaging.py`.

`package_metadata.json` includes:
- `bundle_format_version`
- `connector_target`
- `connector_key`
- `connector_version`
- `manifest_schema_version`
- `sdk_version`
- `runtime_compatibility_range`
- `resource_types`
- operation names and kinds

`checksums.json` currently contains SHA-256 checksums for the bundle files.

## 13. Use the Example Connector

There is a runnable example in:
- `examples/basic_connector.py`

Example commands:

```bash
uv run orbixal-connector describe \
  --connector basic_connector:ExampleConnector

uv run orbixal-connector validate \
  --connector basic_connector:ExampleConnector \
  --config '{"workspace":"demo"}' \
  --auth '{"access_token":"token"}'

uv run orbixal-connector run read \
  --connector basic_connector:ExampleConnector \
  --action get_item \
  --params '{"id":1}' \
  --config '{"workspace":"demo"}' \
  --auth '{"access_token":"token"}'
```

If you run it from outside the examples directory, make sure the module is importable via `PYTHONPATH` or an editable install.

## 14. Recommended Author Workflow

Use this order:

1. run `init`
2. implement `describe()`
3. implement `validate_config()`
4. implement `test_connection()`
5. implement `list_resources()`
6. implement `read()` and `query()`
7. run `validate`
8. run `test-connection`
9. run `read/query`
10. package the connector

That keeps you close to the actual platform contract from the start.

## 15. Current Scope and Limits

What the SDK covers now:
- pull-style connectors
- manifest declaration
- config/auth schema validation
- local execution harness
- packaging bundle generation
- structured errors
- local HTTP client
- scaffold generation

What is still intentionally limited:
- no webhook/event authoring flow yet
- no provider-specific retry policy framework yet
- no artifact signing/provenance yet
- no direct Registry publication flow yet

Those are platform-level concerns or later-phase additions.

# Connector Author SDK

Internal-first SDK for building Orbixal connectors with a future public release path.

Detailed guide:
- `USAGE_GUIDE.md`

Local setup:
- `uv lock`
- `uv sync`
- `uv run python -m unittest discover tests`
- `python3 scripts/sync_canonical_contracts.py --source-repo /path/to/orbixal-data-connector`

Canonical contract sync:
- bundled manifest/result schemas and generated model modules are mirrored from `orbixal-data-connector/schemas/`
- run `make sync-contracts` from this repo root when canonical connector contracts change
- run `make check-contracts` in CI or before release to ensure the vendored mirror has not drifted

Current local workflow:
- `uv run orbixal-connector describe --connector module:ConnectorClass`
- `uv run orbixal-connector validate --connector module:ConnectorClass --config '{"key":"value"}' --auth '{"access_token":"..."}'`
- `uv run orbixal-connector test-connection --connector module:ConnectorClass --config '{}' --auth '{}'`
- `uv run orbixal-connector list-resources --connector module:ConnectorClass --config '{}' --auth '{}'`
- `uv run orbixal-connector run read --connector module:ConnectorClass --action get_item --params '{"id":1}'`
- `uv run orbixal-connector run query --connector module:ConnectorClass --action search --params '{"query":"foo"}'`
- `uv run orbixal-connector package --connector module:ConnectorClass --output-dir ./dist/connector`
- `uv run orbixal-connector init --connector-key my_api --output-dir ./my_connector`

Packaging output:
- `./dist/connector/<connector_key>/<connector_version>/manifest.json`
- `./dist/connector/<connector_key>/<connector_version>/package_metadata.json`
- `./dist/connector/<connector_key>/<connector_version>/checksums.json`

Local `read` and `query` outputs are validated against the canonical `records` and `tabular` schemas before they are emitted.

The SDK also ships:
- a default local HTTP client for connector development
- structured connector exception types for sanitized failures
- a scaffold generator for new connector packages
- OAuth auth-schema helpers such as `oauth2_auth()` for declaring resolved auth needs

OAuth note:
- connector manifests may declare OAuth requirements and non-secret metadata
- OAuth app credentials and callbacks are backend-owned
- never put `client_id`, `client_secret`, callback URLs, access tokens, or refresh tokens
  in a manifest or package

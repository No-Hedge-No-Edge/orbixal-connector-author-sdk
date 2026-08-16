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
- `ORBIXAL_CONNECTOR_SIGNING_SECRET=... uv run orbixal-connector release-metadata --package-dir ./dist/connector/<connector_key>/<connector_version>`
- `uv run orbixal-connector inspect-artifact --package-dir ./dist/connector/<connector_key>/<connector_version>`
- `uv run orbixal-connector verify-artifact --package-dir ./dist/connector/<connector_key>/<connector_version>`
- `uv run orbixal-connector publish-local --package-dir ./dist/connector/<connector_key>/<connector_version> --registry-url http://localhost:8000/api/v1`
- `uv run orbixal-connector init --connector-key my_api --output-dir ./my_connector`

Packaging output:
- `./dist/connector/<connector_key>/<connector_version>/manifest.json`
- `./dist/connector/<connector_key>/<connector_version>/package_metadata.json`
- `./dist/connector/<connector_key>/<connector_version>/connector_code.zip`
- `./dist/connector/<connector_key>/<connector_version>/sbom.json`
- `./dist/connector/<connector_key>/<connector_version>/checksums.json`
- mandatory policy metadata: `egress_policy.json`
- optional third-party release metadata: `signature.json`, `vulnerability_scan.json`,
  `malware_scan.json`, and `provenance.json`

By default, packaging infers the connector module or package source from the
`module:Class` target. For production package layouts, pass one or more
`--source` values to include the exact importable package directory or source
file:

```bash
uv run orbixal-connector package \
  --connector my_connector.connector:MyConnector \
  --source ./src/my_connector \
  --output-dir ./dist/connector
```

Local publication helper:

```bash
uv run orbixal-connector publish-local \
  --package-dir ./dist/connector/<connector_key>/<connector_version> \
  --registry-url http://localhost:8000/api/v1 \
  --approve
```

`publish-local` is only for dev/local registry flows where the registry service
can read the same package directory path. Production publication should use a
registry upload intent or pre-signed object-store upload.

Third-party publication gate metadata:

```bash
ORBIXAL_CONNECTOR_SIGNING_SECRET=... uv run orbixal-connector release-metadata \
  --package-dir ./dist/connector/<connector_key>/<connector_version> \
  --source-ref git+https://github.com/publisher/connector@<sha>
```

The manifest is the source of truth for the default-deny egress policy.
Packaging writes the policy sidecar. Release metadata writes signed scanner
attestations and provenance, refreshes `checksums.json`, and regenerates
`signature.json` so the registry can verify the submitted release-gate evidence.
An optional `--allowed-host` may assert that a host is already declared; it does
not broaden or rewrite the manifest policy.

Connector configuration is closed by the platform. `config_schema` remains
required: use `{"type": "object", "properties": {}}` when the connector has no
configuration, or declare every accepted key under `properties`. Publishers
must not declare the JSON Schema `additionalProperties` keyword; SDK and backend
validation reject it, and undeclared configuration keys are denied at runtime.

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

# Example Connector

The example connector is intentionally small and local-only. It shows the minimum
shape expected by the Author SDK: manifest, config validation, connection test,
resource listing, read, and query.

Example commands after installing the SDK:

```bash
uv run orbixal-connector describe --connector basic_connector:ExampleConnector
uv run orbixal-connector validate --connector basic_connector:ExampleConnector --config '{"workspace":"demo"}' --auth '{"access_token":"token"}'
uv run orbixal-connector run read --connector basic_connector:ExampleConnector --action get_item --params '{"id":1}' --config '{"workspace":"demo"}' --auth '{"access_token":"token"}'
uv run orbixal-connector package --connector basic_connector:ExampleConnector --output-dir ./dist/example
```

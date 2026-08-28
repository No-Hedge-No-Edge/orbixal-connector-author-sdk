"""Connector package scaffolding helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _class_name(connector_key: str) -> str:
    return "".join(part.capitalize() for part in connector_key.split("_")) + "Connector"


@dataclass(frozen=True, slots=True)
class ScaffoldArtifact:
    connector_key: str
    package_name: str
    class_name: str
    root_dir: str
    connector_file: str
    pyproject_file: str
    readme_file: str

    def to_dict(self) -> dict[str, str]:
        return {
            "connector_key": self.connector_key,
            "package_name": self.package_name,
            "class_name": self.class_name,
            "root_dir": self.root_dir,
            "connector_file": self.connector_file,
            "pyproject_file": self.pyproject_file,
            "readme_file": self.readme_file,
        }


def scaffold_connector(
    *,
    connector_key: str,
    output_dir: str | Path,
    package_name: str | None = None,
    class_name: str | None = None,
) -> ScaffoldArtifact:
    if not _KEY_RE.match(connector_key):
        raise ValueError("connector_key must match ^[a-z][a-z0-9_]*$")

    resolved_package_name = package_name or f"orbixal_connector_{connector_key}"
    resolved_class_name = class_name or _class_name(connector_key)
    root = Path(output_dir)
    src_dir = root / "src" / resolved_package_name
    tests_dir = root / "tests"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "__init__.py").write_text(
        f"from {resolved_package_name}.connector import {resolved_class_name}\n",
        encoding="utf-8",
    )
    connector_file = src_dir / "connector.py"
    connector_file.write_text(
        _connector_template(
            connector_key=connector_key,
            class_name=resolved_class_name,
        ),
        encoding="utf-8",
    )
    pyproject_file = root / "pyproject.toml"
    pyproject_file.write_text(
        _pyproject_template(package_name=resolved_package_name),
        encoding="utf-8",
    )
    readme_file = root / "README.md"
    readme_file.write_text(
        _readme_template(connector_key=connector_key, class_name=resolved_class_name),
        encoding="utf-8",
    )
    (tests_dir / "test_connector.py").write_text(
        _test_template(
            package_name=resolved_package_name,
            class_name=resolved_class_name,
        ),
        encoding="utf-8",
    )

    return ScaffoldArtifact(
        connector_key=connector_key,
        package_name=resolved_package_name,
        class_name=resolved_class_name,
        root_dir=str(root),
        connector_file=str(connector_file),
        pyproject_file=str(pyproject_file),
        readme_file=str(readme_file),
    )


def _connector_template(*, connector_key: str, class_name: str) -> str:
    title_name = connector_key.replace("_", " ").title()
    return f'''from typing import Any, Mapping

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
    ValidationResult,
    build_manifest,
    no_egress,
    oauth2_auth,
    query_operation,
    read_operation,
)


class {class_name}(Connector):
    def describe(self):
        return build_manifest(
            key="{connector_key}",
            name="{title_name}",
            version="0.1.1",
            manifest_schema_version="2026-01",
            sdk_version="0.1.5",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get", "search", "resource_list"],
            auth_schema=oauth2_auth(),
            egress_policy=no_egress(),
            config_schema={{
                "type": "object",
                "properties": {{"workspace": {{"type": "string"}}}},
                "required": ["workspace"],
            }},
            resource_types=["item"],
            operations=[
                read_operation(
                    name="get_item",
                    input_schema={{
                        "type": "object",
                        "properties": {{"id": {{"type": "integer"}}}},
                        "required": ["id"],
                    }},
                ),
                query_operation(
                    name="search_items",
                    input_schema={{
                        "type": "object",
                        "properties": {{"query": {{"type": "string"}}}},
                        "required": ["query"],
                    }},
                ),
            ],
        )

    def validate_config(self, config: Mapping[str, Any]) -> ValidationResult:
        return ValidationResult.ok()

    def test_connection(self, ctx: ConnectorContext) -> ConnectionTestResult:
        has_token = bool(ctx.auth.get("access_token"))
        return ConnectionTestResult(
            success=has_token,
            summary="connected" if has_token else "missing token",
            error_code=None if has_token else "missing_token",
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
                    attributes={{"workspace": ctx.config.get("workspace")}},
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
                    attributes={{"workspace": ctx.config.get("workspace")}},
                )
            ]
        )

    def query(self, ctx: ConnectorContext, request: QueryRequest):
        return TabularResult(
            columns=[ColumnDef(name="query", type="string")],
            rows=[RowItem(row_id="1", values={{"query": request.params["query"]}})],
        )
'''


def _pyproject_template(*, package_name: str) -> str:
    return f'''[build-system]
requires = ["hatchling>=1.25.0"]
build-backend = "hatchling.build"

[project]
name = "{package_name}"
version = "0.1.5"
requires-python = ">=3.12"
dependencies = ["orbixal-connector-author-sdk>=0.1.5"]

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]
'''


def _readme_template(*, connector_key: str, class_name: str) -> str:
    return f"""# {connector_key.replace('_', ' ').title()}

Generated connector scaffold for `{connector_key}`.

Main class: `{class_name}`
"""


def _test_template(*, package_name: str, class_name: str) -> str:
    return f"""from {package_name} import {class_name}


def test_connector_describe():
    connector = {class_name}()
    manifest = connector.describe()
    assert manifest.key
"""


__all__ = ["ScaffoldArtifact", "scaffold_connector"]

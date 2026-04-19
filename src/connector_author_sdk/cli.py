"""CLI for local connector author workflows."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import click

from connector_author_sdk.errors import ConnectorError
from connector_author_sdk.harness import (
    describe_connector,
    load_connector,
    run_list_resources,
    run_query,
    run_read,
    run_test_connection,
    validate_connector,
)
from connector_author_sdk.packaging import package_connector
from connector_author_sdk.scaffold import scaffold_connector


def _json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    raw = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return parsed


def _emit(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


def _emit_error(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, indent=2, sort_keys=True), err=True)


def _with_error_handling(func):
    def wrapper(*args: Any, **kwargs: Any) -> int:
        try:
            return int(func(*args, **kwargs))
        except ConnectorError as exc:
            _emit_error(exc.to_dict())
            return 2
        except Exception as exc:  # pragma: no cover - defensive boundary
            _emit_error(
                {
                    "error": {
                        "code": "sdk_error",
                        "message": str(exc),
                        "details": {"type": exc.__class__.__name__},
                    }
                }
            )
            return 2

    return wrapper


@click.group()
def cli() -> None:
    """Orbixal connector author tooling."""


@cli.command("describe")
@click.option("--connector", required=True)
def describe_command(connector: str) -> int:
    return _describe_command(connector=connector)


@_with_error_handling
def _describe_command(*, connector: str) -> int:
    loaded_connector = load_connector(connector)
    _emit(describe_connector(loaded_connector))
    return 0


@cli.command("validate")
@click.option("--connector", required=True)
@click.option("--config")
@click.option("--auth")
def validate_command(connector: str, config: str | None, auth: str | None) -> int:
    return _validate_command(connector=connector, config=config, auth=auth)


@_with_error_handling
def _validate_command(*, connector: str, config: str | None, auth: str | None) -> int:
    loaded_connector = load_connector(connector)
    report = validate_connector(
        loaded_connector,
        config=_json_arg(config),
        auth_payload=_json_arg(auth),
    )
    _emit(report.to_dict())
    return 0 if report.valid else 1


@cli.command("test-connection")
@click.option("--connector", required=True)
@click.option("--config")
@click.option("--auth")
@click.option("--auth-type")
@click.option("--instance-id", default="local-instance", show_default=True)
@click.option("--owner-type", default="user", show_default=True)
@click.option("--owner-id", default="local-user", show_default=True)
@click.option("--execution-id", default="local-execution", show_default=True)
def test_connection_command(
    connector: str,
    config: str | None,
    auth: str | None,
    auth_type: str | None,
    instance_id: str,
    owner_type: str,
    owner_id: str,
    execution_id: str,
) -> int:
    return _test_connection_command(
        connector=connector,
        config=config,
        auth=auth,
        auth_type=auth_type,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
    )


@_with_error_handling
def _test_connection_command(**kwargs: Any) -> int:
    loaded_connector = load_connector(kwargs["connector"])
    result = run_test_connection(
        loaded_connector,
        config=_json_arg(kwargs["config"]),
        auth_payload=_json_arg(kwargs["auth"]),
        auth_type=kwargs["auth_type"],
        instance_id=kwargs["instance_id"],
        owner_type=kwargs["owner_type"],
        owner_id=kwargs["owner_id"],
        execution_id=kwargs["execution_id"],
    )
    _emit(result)
    return 0 if result["success"] else 1


@cli.command("list-resources")
@click.option("--connector", required=True)
@click.option("--config")
@click.option("--auth")
@click.option("--auth-type")
@click.option("--query")
@click.option("--instance-id", default="local-instance", show_default=True)
@click.option("--owner-type", default="user", show_default=True)
@click.option("--owner-id", default="local-user", show_default=True)
@click.option("--execution-id", default="local-execution", show_default=True)
def list_resources_command(
    connector: str,
    config: str | None,
    auth: str | None,
    auth_type: str | None,
    query: str | None,
    instance_id: str,
    owner_type: str,
    owner_id: str,
    execution_id: str,
) -> int:
    return _list_resources_command(
        connector=connector,
        config=config,
        auth=auth,
        auth_type=auth_type,
        query=query,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
    )


@_with_error_handling
def _list_resources_command(**kwargs: Any) -> int:
    loaded_connector = load_connector(kwargs["connector"])
    _emit(
        run_list_resources(
            loaded_connector,
            config=_json_arg(kwargs["config"]),
            auth_payload=_json_arg(kwargs["auth"]),
            auth_type=kwargs["auth_type"],
            query=_json_arg(kwargs["query"]),
            instance_id=kwargs["instance_id"],
            owner_type=kwargs["owner_type"],
            owner_id=kwargs["owner_id"],
            execution_id=kwargs["execution_id"],
        )
    )
    return 0


@cli.command("package")
@click.option("--connector", required=True)
@click.option("--output-dir", required=True)
def package_command(connector: str, output_dir: str) -> int:
    return _package_command(connector=connector, output_dir=output_dir)


@_with_error_handling
def _package_command(*, connector: str, output_dir: str) -> int:
    loaded_connector = load_connector(connector)
    artifact = package_connector(
        loaded_connector,
        connector_target=connector,
        output_dir=output_dir,
    )
    _emit(artifact.to_dict())
    return 0


@cli.command("init")
@click.option("--connector-key", required=True)
@click.option("--output-dir", required=True)
@click.option("--package-name")
@click.option("--class-name")
def init_command(
    connector_key: str,
    output_dir: str,
    package_name: str | None,
    class_name: str | None,
) -> int:
    return _init_command(
        connector_key=connector_key,
        output_dir=output_dir,
        package_name=package_name,
        class_name=class_name,
    )


@_with_error_handling
def _init_command(
    *,
    connector_key: str,
    output_dir: str,
    package_name: str | None,
    class_name: str | None,
) -> int:
    artifact = scaffold_connector(
        connector_key=connector_key,
        output_dir=output_dir,
        package_name=package_name,
        class_name=class_name,
    )
    _emit(artifact.to_dict())
    return 0


@cli.group("run")
def run_group() -> None:
    """Run connector actions locally."""


@run_group.command("read")
@click.option("--connector", required=True)
@click.option("--action", required=True)
@click.option("--params")
@click.option("--config")
@click.option("--auth")
@click.option("--auth-type")
@click.option("--instance-id", default="local-instance", show_default=True)
@click.option("--owner-type", default="user", show_default=True)
@click.option("--owner-id", default="local-user", show_default=True)
@click.option("--execution-id", default="local-execution", show_default=True)
@click.option("--include-raw", is_flag=True)
def run_read_command(
    connector: str,
    action: str,
    params: str | None,
    config: str | None,
    auth: str | None,
    auth_type: str | None,
    instance_id: str,
    owner_type: str,
    owner_id: str,
    execution_id: str,
    include_raw: bool,
) -> int:
    return _run_read_command(
        connector=connector,
        action=action,
        params=params,
        config=config,
        auth=auth,
        auth_type=auth_type,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
        include_raw=include_raw,
    )


@_with_error_handling
def _run_read_command(**kwargs: Any) -> int:
    loaded_connector = load_connector(kwargs["connector"])
    _emit(
        run_read(
            loaded_connector,
            action=kwargs["action"],
            params=_json_arg(kwargs["params"]),
            config=_json_arg(kwargs["config"]),
            auth_payload=_json_arg(kwargs["auth"]),
            auth_type=kwargs["auth_type"],
            instance_id=kwargs["instance_id"],
            owner_type=kwargs["owner_type"],
            owner_id=kwargs["owner_id"],
            execution_id=kwargs["execution_id"],
            include_raw=kwargs["include_raw"],
        )
    )
    return 0


@run_group.command("query")
@click.option("--connector", required=True)
@click.option("--action", required=True)
@click.option("--params")
@click.option("--config")
@click.option("--auth")
@click.option("--auth-type")
@click.option("--instance-id", default="local-instance", show_default=True)
@click.option("--owner-type", default="user", show_default=True)
@click.option("--owner-id", default="local-user", show_default=True)
@click.option("--execution-id", default="local-execution", show_default=True)
@click.option("--include-raw", is_flag=True)
@click.option("--cursor")
def run_query_command(
    connector: str,
    action: str,
    params: str | None,
    config: str | None,
    auth: str | None,
    auth_type: str | None,
    instance_id: str,
    owner_type: str,
    owner_id: str,
    execution_id: str,
    include_raw: bool,
    cursor: str | None,
) -> int:
    return _run_query_command(
        connector=connector,
        action=action,
        params=params,
        config=config,
        auth=auth,
        auth_type=auth_type,
        instance_id=instance_id,
        owner_type=owner_type,
        owner_id=owner_id,
        execution_id=execution_id,
        include_raw=include_raw,
        cursor=cursor,
    )


@_with_error_handling
def _run_query_command(**kwargs: Any) -> int:
    loaded_connector = load_connector(kwargs["connector"])
    _emit(
        run_query(
            loaded_connector,
            action=kwargs["action"],
            params=_json_arg(kwargs["params"]),
            config=_json_arg(kwargs["config"]),
            auth_payload=_json_arg(kwargs["auth"]),
            auth_type=kwargs["auth_type"],
            instance_id=kwargs["instance_id"],
            owner_type=kwargs["owner_type"],
            owner_id=kwargs["owner_id"],
            execution_id=kwargs["execution_id"],
            include_raw=kwargs["include_raw"],
            cursor=kwargs["cursor"],
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    return int(
        cli.main(
            args=argv,
            prog_name="orbixal-connector",
            standalone_mode=False,
        )
        or 0
    )


if __name__ == "__main__":
    raise SystemExit(main())

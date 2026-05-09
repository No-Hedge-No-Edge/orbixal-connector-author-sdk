"""CLI for local connector author workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import httpx

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
from connector_author_sdk.packaging import (
    inspect_package_artifact,
    package_connector,
    verify_package_artifact,
)
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


def _registry_response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "Registry returned an empty error response."
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        error_payload = payload.get("error")
        if isinstance(error_payload, dict) and isinstance(error_payload.get("message"), str):
            return error_payload["message"]
    return response.text or "Registry returned an error response."


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
@click.option(
    "--source",
    "sources",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Source file or package directory to include in the executable bundle. May be repeated.",
)
def package_command(connector: str, output_dir: str, sources: tuple[Path, ...]) -> int:
    return _package_command(connector=connector, output_dir=output_dir, sources=sources)


@_with_error_handling
def _package_command(*, connector: str, output_dir: str, sources: tuple[Path, ...] = ()) -> int:
    loaded_connector = load_connector(connector)
    artifact = package_connector(
        loaded_connector,
        connector_target=connector,
        output_dir=output_dir,
        source_paths=sources or None,
    )
    _emit(artifact.to_dict())
    return 0


@cli.command("inspect-artifact")
@click.option("--package-dir", required=True, type=click.Path(exists=True, path_type=Path))
def inspect_artifact_command(package_dir: Path) -> int:
    return _inspect_artifact_command(package_dir=package_dir)


@_with_error_handling
def _inspect_artifact_command(*, package_dir: Path) -> int:
    _emit(inspect_package_artifact(package_dir))
    return 0


@cli.command("verify-artifact")
@click.option("--package-dir", required=True, type=click.Path(exists=True, path_type=Path))
def verify_artifact_command(package_dir: Path) -> int:
    return _verify_artifact_command(package_dir=package_dir)


@_with_error_handling
def _verify_artifact_command(*, package_dir: Path) -> int:
    _emit(verify_package_artifact(package_dir))
    return 0


@cli.command("publish-local")
@click.option(
    "--package-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Packaged connector directory visible to the registry service filesystem.",
)
@click.option(
    "--registry-url",
    default="http://localhost:8000/api/v1",
    show_default=True,
    help="Connector registry/control-plane API base URL.",
)
@click.option("--publisher-type", default="first_party", show_default=True)
@click.option("--publisher-id", default="orbixal", show_default=True)
@click.option("--visibility", default="internal", show_default=True)
@click.option("--actor-type")
@click.option("--actor-id")
@click.option("--approve/--no-approve", default=False, show_default=True)
@click.option("--set-as-default/--no-set-as-default", default=True, show_default=True)
@click.option("--set-as-latest/--no-set-as-latest", default=True, show_default=True)
def publish_local_command(
    package_dir: Path,
    registry_url: str,
    publisher_type: str,
    publisher_id: str,
    visibility: str,
    actor_type: str | None,
    actor_id: str | None,
    approve: bool,
    set_as_default: bool,
    set_as_latest: bool,
) -> int:
    return _publish_local_command(
        package_dir=package_dir,
        registry_url=registry_url,
        publisher_type=publisher_type,
        publisher_id=publisher_id,
        visibility=visibility,
        actor_type=actor_type,
        actor_id=actor_id,
        approve=approve,
        set_as_default=set_as_default,
        set_as_latest=set_as_latest,
    )


@_with_error_handling
def _publish_local_command(
    *,
    package_dir: Path,
    registry_url: str,
    publisher_type: str,
    publisher_id: str,
    visibility: str,
    actor_type: str | None,
    actor_id: str | None,
    approve: bool,
    set_as_default: bool,
    set_as_latest: bool,
) -> int:
    payload = publish_local_package(
        package_dir=package_dir,
        registry_url=registry_url,
        publisher_type=publisher_type,
        publisher_id=publisher_id,
        visibility=visibility,
        actor_type=actor_type,
        actor_id=actor_id,
        approve=approve,
        set_as_default=set_as_default,
        set_as_latest=set_as_latest,
    )
    _emit(payload)
    return 0


def publish_local_package(
    *,
    package_dir: Path,
    registry_url: str,
    publisher_type: str = "first_party",
    publisher_id: str = "orbixal",
    visibility: str = "internal",
    actor_type: str | None = None,
    actor_id: str | None = None,
    approve: bool = False,
    set_as_default: bool = True,
    set_as_latest: bool = True,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Submit a local package directory to a registry API and optionally approve it."""

    base_url = registry_url.rstrip("/")
    submission_payload = {
        "package_dir": str(package_dir.expanduser().resolve()),
        "publisher_type": publisher_type,
        "publisher_id": publisher_id,
        "visibility": visibility,
        "actor_type": actor_type,
        "actor_id": actor_id,
    }
    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=30)
    try:
        submission = _registry_json_request(
            client,
            "POST",
            f"{base_url}/connectors/publication-submissions/local-package",
            json_payload=submission_payload,
        )
        result: dict[str, Any] = {"submission": submission}
        if approve:
            submission_id = submission.get("id")
            if not isinstance(submission_id, str) or not submission_id:
                raise ConnectorError(
                    code="registry_publication_failed",
                    message="Registry submission response did not include an id.",
                    details={"registry_url": base_url},
                )
            approval = _registry_json_request(
                client,
                "POST",
                f"{base_url}/connectors/publication-submissions/{submission_id}/approve",
                json_payload={
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                    "set_as_default": set_as_default,
                    "set_as_latest": set_as_latest,
                },
            )
            result["approval"] = approval
        return result
    finally:
        if owns_client:
            client.close()


def _registry_json_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = client.request(method, url, json=json_payload)
    except httpx.HTTPError as exc:
        raise ConnectorError(
            code="registry_unavailable",
            message=f"Registry request failed: {exc}",
            details={"url": url},
        ) from exc
    if not response.is_success:
        raise ConnectorError(
            code="registry_publication_failed",
            message=_registry_response_detail(response),
            details={"url": url, "status_code": response.status_code},
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise ConnectorError(
            code="registry_publication_failed",
            message="Registry returned a non-object JSON response.",
            details={"url": url},
        )
    return payload


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

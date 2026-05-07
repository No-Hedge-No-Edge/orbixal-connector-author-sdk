import unittest

from connector_author_sdk.manifests import (
    build_manifest,
    oauth2_auth,
    query_operation,
    read_operation,
)
from connector_author_sdk.validation import (
    validate_auth_payload,
    validate_config,
    validate_manifest,
)


class ManifestValidationTests(unittest.TestCase):
    def test_manifest_build_and_validate(self) -> None:
        manifest = build_manifest(
            key="github",
            name="GitHub",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get", "search"],
            auth_schema={
                "type": "oauth2",
                "required_fields": ["access_token"],
            },
            config_schema={
                "type": "object",
                "properties": {"default_owner": {"type": "string"}},
                "required": ["default_owner"],
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

        result = validate_manifest(manifest)
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_config_validation_reports_missing_required_fields(self) -> None:
        manifest = build_manifest(
            key="github",
            name="GitHub",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get"],
            auth_schema={"type": "none"},
            config_schema={
                "type": "object",
                "properties": {"default_owner": {"type": "string"}},
                "required": ["default_owner"],
            },
            resource_types=["issue"],
            operations=[
                read_operation(
                    name="get_issue",
                    input_schema={"type": "object"},
                )
            ],
        )

        result = validate_config({}, manifest)
        self.assertFalse(result.valid)
        self.assertTrue(result.errors)

    def test_oauth2_auth_helper_builds_backend_compatible_schema(self) -> None:
        manifest = build_manifest(
            key="github",
            name="GitHub",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get"],
            auth_schema=oauth2_auth(provider="github", default_scopes=["repo"]),
            config_schema={"type": "object"},
            resource_types=["issue"],
            operations=[read_operation(name="get_issue", input_schema={"type": "object"})],
        )

        manifest_result = validate_manifest(manifest)
        self.assertTrue(manifest_result.valid)
        self.assertEqual(
            manifest.auth_schema,
            {
                "type": "oauth2",
                "required_fields": ["access_token"],
                "optional_fields": ["refresh_token", "expires_at", "scopes"],
                "provider": "github",
                "default_scopes": ["repo"],
            },
        )

        auth_result = validate_auth_payload({"access_token": "token"}, manifest)
        self.assertTrue(auth_result.valid)

    def test_oauth2_auth_schema_requires_access_token(self) -> None:
        manifest = build_manifest(
            key="github",
            name="GitHub",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get"],
            auth_schema=oauth2_auth(required_fields=["token"]),
            config_schema={"type": "object"},
            resource_types=["issue"],
            operations=[read_operation(name="get_issue", input_schema={"type": "object"})],
        )

        result = validate_manifest(manifest)
        self.assertFalse(result.valid)
        self.assertEqual(result.errors[0].field, "auth_schema.required_fields")

    def test_manifest_validation_rejects_client_secret(self) -> None:
        manifest = build_manifest(
            key="github",
            name="GitHub",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get"],
            auth_schema={
                **oauth2_auth(),
                "client_secret": "do-not-ship",
            },
            config_schema={"type": "object"},
            resource_types=["issue"],
            operations=[read_operation(name="get_issue", input_schema={"type": "object"})],
        )

        result = validate_manifest(manifest)
        self.assertFalse(result.valid)
        self.assertEqual(result.errors[0].field, "$.auth_schema.client_secret")

    def test_oauth2_auth_schema_rejects_backend_managed_app_fields(self) -> None:
        manifest = build_manifest(
            key="github",
            name="GitHub",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get"],
            auth_schema={
                **oauth2_auth(),
                "client_id": "backend-managed",
                "callback_url": "https://example.com/callback",
            },
            config_schema={"type": "object"},
            resource_types=["issue"],
            operations=[read_operation(name="get_issue", input_schema={"type": "object"})],
        )

        result = validate_manifest(manifest)
        self.assertFalse(result.valid)
        self.assertEqual(
            [error.field for error in result.errors],
            ["auth_schema.client_id", "auth_schema.callback_url"],
        )

    def test_platform_auth_payload_rejects_unexpected_fields(self) -> None:
        manifest = build_manifest(
            key="github",
            name="GitHub",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["record_get"],
            auth_schema=oauth2_auth(),
            config_schema={"type": "object"},
            resource_types=["issue"],
            operations=[read_operation(name="get_issue", input_schema={"type": "object"})],
        )

        result = validate_auth_payload({"access_token": "token", "client_secret": "bad"}, manifest)
        self.assertFalse(result.valid)
        self.assertEqual(result.errors[0].field, "client_secret")

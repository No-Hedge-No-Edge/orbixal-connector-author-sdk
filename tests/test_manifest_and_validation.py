import unittest

from connector_author_sdk.manifests import build_manifest, query_operation, read_operation
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

    def test_auth_payload_validation_uses_manifest_descriptor(self) -> None:
        manifest = build_manifest(
            key="macro",
            name="Macro",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["search"],
            auth_schema={"type": "api_key", "required_fields": ["api_key"]},
            config_schema={"type": "object"},
            resource_types=["series"],
            operations=[
                read_operation(
                    name="get_series",
                    input_schema={"type": "object"},
                )
            ],
        )

        missing = validate_auth_payload({}, manifest)
        self.assertFalse(missing.valid)
        self.assertEqual(missing.errors[0].field, "api_key")

        valid = validate_auth_payload({"api_key": "secret"}, manifest)
        self.assertTrue(valid.valid)

    def test_authless_manifest_rejects_non_empty_auth_payload(self) -> None:
        manifest = build_manifest(
            key="sec",
            name="SEC",
            version="1.0.0",
            manifest_schema_version="2026-01",
            sdk_version="1.0.0",
            runtime_compatibility_range=">=1.0,<2.0",
            capabilities=["search"],
            auth_schema={"type": "none"},
            config_schema={"type": "object"},
            resource_types=["filing"],
            operations=[
                read_operation(
                    name="get_filing",
                    input_schema={"type": "object"},
                )
            ],
        )

        result = validate_auth_payload({"token": "should-not-be-here"}, manifest)
        self.assertFalse(result.valid)
        self.assertEqual(result.errors[0].field, "$")

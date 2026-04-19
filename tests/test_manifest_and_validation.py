import unittest

from connector_author_sdk.manifests import build_manifest, query_operation, read_operation
from connector_author_sdk.validation import validate_config, validate_manifest


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
                "type": "object",
                "properties": {"access_token": {"type": "string"}},
                "required": ["access_token"],
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
            auth_schema={"type": "object"},
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

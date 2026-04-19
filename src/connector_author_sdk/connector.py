"""Base connector interface for Orbixal connector authors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from connector_author_sdk.context import ConnectorContext
from connector_author_sdk.manifests.models import ConnectorManifest
from connector_author_sdk.results.models import (
    ConnectionTestResult,
    ConnectorResult,
    QueryRequest,
    ReadRequest,
    ResourcePage,
)
from connector_author_sdk.validation import ValidationResult


class Connector(ABC):
    """Minimal stable authoring interface for pull-style connectors."""

    @abstractmethod
    def describe(self) -> ConnectorManifest:
        """Return the connector manifest for this implementation."""

    @abstractmethod
    def validate_config(self, config: Mapping[str, Any]) -> ValidationResult:
        """Perform semantic config validation beyond pure JSON Schema checks."""

    @abstractmethod
    def test_connection(self, ctx: ConnectorContext) -> ConnectionTestResult:
        """Validate provider connectivity and authorization using resolved auth."""

    @abstractmethod
    def list_resources(
        self,
        ctx: ConnectorContext,
        query: Mapping[str, Any] | None = None,
    ) -> ResourcePage:
        """Return provider resources used for discovery flows."""

    @abstractmethod
    def read(self, ctx: ConnectorContext, request: ReadRequest) -> ConnectorResult:
        """Execute a targeted read action."""

    @abstractmethod
    def query(self, ctx: ConnectorContext, request: QueryRequest) -> ConnectorResult:
        """Execute a broader search or scan action."""

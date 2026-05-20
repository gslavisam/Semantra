"""Repository helpers for SQLite-backed catalog discovery and concept usage read models."""

from __future__ import annotations

from app.models.knowledge import CanonicalConceptUsageRecord
from app.models.mapping import CatalogConceptDetail, CatalogIntegrationDetail, CatalogIntegrationRecord
from app.services.persistence_service import SQLitePersistenceService, persistence_service


class CatalogRepository:
    """Provide a narrow persistence surface for catalog discovery queries."""

    def __init__(self, storage: SQLitePersistenceService | None = None) -> None:
        self._storage = storage or persistence_service

    def list_integrations(
        self,
        *,
        source_system: str | None = None,
        target_system: str | None = None,
        business_domain: str | None = None,
        owner: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
        integration_name: str | None = None,
    ) -> list[CatalogIntegrationRecord]:
        """List catalog integrations from the normalized discovery read model."""

        return self._storage.list_catalog_integrations(
            source_system=source_system,
            target_system=target_system,
            business_domain=business_domain,
            owner=owner,
            status=status,
            artifact_type=artifact_type,
            integration_name=integration_name,
        )

    def search_integrations(
        self,
        query_text: str,
        *,
        source_system: str | None = None,
        target_system: str | None = None,
        business_domain: str | None = None,
        owner: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> list[CatalogIntegrationRecord]:
        """Search catalog integrations using the normalized discovery read model."""

        return self._storage.search_catalog_integrations(
            query_text,
            source_system=source_system,
            target_system=target_system,
            business_domain=business_domain,
            owner=owner,
            status=status,
            artifact_type=artifact_type,
        )

    def get_integration_detail(self, integration_name: str) -> CatalogIntegrationDetail:
        """Return one integration detail record from the catalog read model."""

        return self._storage.get_catalog_integration_detail(integration_name)

    def get_concept_detail(
        self,
        concept_id: str,
        *,
        source_system: str | None = None,
        target_system: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> CatalogConceptDetail:
        """Return concept-centric catalog usage detail from the normalized read model."""

        return self._storage.get_catalog_concept_detail(
            concept_id,
            source_system=source_system,
            target_system=target_system,
            status=status,
            artifact_type=artifact_type,
        )

    def list_concept_usage_counts(self) -> dict[str, int]:
        """Return concept usage counts derived from catalog projection rows."""

        return self._storage.list_catalog_concept_usage_counts()

    def list_concept_usage_facets(self) -> dict[str, dict[str, list[str]]]:
        """Return discovery facets for canonical concepts derived from catalog projections."""

        return self._storage.list_catalog_concept_usage_facets()

    def list_concept_usage_records(
        self,
        concept_id: str,
        *,
        source_system: str | None = None,
        target_system: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> list[CanonicalConceptUsageRecord]:
        """Return concept usage rows for one canonical concept from the catalog projection."""

        return self._storage.list_catalog_concept_usage_records(
            concept_id,
            source_system=source_system,
            target_system=target_system,
            status=status,
            artifact_type=artifact_type,
        )


catalog_repository = CatalogRepository()

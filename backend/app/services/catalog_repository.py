"""Repository helpers for SQLite-backed catalog discovery and concept usage read models."""

from __future__ import annotations

from app.models.knowledge import CanonicalConceptUsageRecord
from app.models.mapping import (
    CatalogFieldReuseCandidate,
    CatalogFieldReuseMatch,
    CatalogFieldReuseSelection,
    CatalogFieldReuseShortlistResponse,
    CatalogConceptDetail,
    CatalogIntegrationCompareResponse,
    CatalogIntegrationDetail,
    CatalogIntegrationRecord,
    CatalogWorkspaceReuseCandidate,
    CatalogWorkspaceReuseShortlistResponse,
)
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

    def compare_integrations(self, base_integration_name: str, peer_integration_name: str) -> CatalogIntegrationCompareResponse:
        """Build a deterministic compare summary between two named integrations."""

        base_detail = self.get_integration_detail(base_integration_name)
        peer_detail = self.get_integration_detail(peer_integration_name)

        base_concepts = {str(concept).strip() for concept in base_detail.canonical_concepts if str(concept).strip()}
        peer_concepts = {str(concept).strip() for concept in peer_detail.canonical_concepts if str(concept).strip()}
        shared_concepts = sorted(base_concepts & peer_concepts)
        base_only_concepts = sorted(base_concepts - peer_concepts)
        peer_only_concepts = sorted(peer_concepts - base_concepts)

        same_source_system = bool(base_detail.source_system and peer_detail.source_system and base_detail.source_system == peer_detail.source_system)
        same_target_system = bool(base_detail.target_system and peer_detail.target_system and base_detail.target_system == peer_detail.target_system)
        same_business_domain = bool(
            base_detail.business_domain and peer_detail.business_domain and base_detail.business_domain == peer_detail.business_domain
        )
        same_artifact_type = base_detail.latest_version.artifact_type == peer_detail.latest_version.artifact_type

        compare_summary_parts: list[str] = []
        compare_summary_parts.append(f"Shared concepts: {len(shared_concepts)}")
        if same_source_system and same_target_system:
            compare_summary_parts.append("same source-target system pair")
        elif same_business_domain:
            compare_summary_parts.append("same business domain")
        if not same_artifact_type:
            compare_summary_parts.append("different artifact type")
        if base_only_concepts:
            compare_summary_parts.append(f"base-only concepts: {len(base_only_concepts)}")
        if peer_only_concepts:
            compare_summary_parts.append(f"peer-only concepts: {len(peer_only_concepts)}")

        suggested_next_actions: list[str] = []
        if shared_concepts:
            suggested_next_actions.append("Open version diff between latest approved versions before reuse.")
        if same_source_system and same_target_system:
            suggested_next_actions.append("Prioritize this compare for direct Workspace reuse candidate review.")
        else:
            suggested_next_actions.append("Validate system and domain context alignment before applying reuse.")
        if base_only_concepts or peer_only_concepts:
            suggested_next_actions.append("Inspect concept-only deltas to avoid cross-domain drift.")

        return CatalogIntegrationCompareResponse(
            base_integration=base_detail,
            peer_integration=peer_detail,
            shared_concepts=shared_concepts,
            base_only_concepts=base_only_concepts,
            peer_only_concepts=peer_only_concepts,
            same_source_system=same_source_system,
            same_target_system=same_target_system,
            same_business_domain=same_business_domain,
            same_artifact_type=same_artifact_type,
            compare_summary="; ".join(compare_summary_parts),
            suggested_next_actions=suggested_next_actions,
        )

    def workspace_reuse_shortlist(
        self,
        *,
        workspace_context: dict,
        top_n: int = 5,
    ) -> CatalogWorkspaceReuseShortlistResponse:
        """Rank approved catalog integrations against workspace context for reuse discovery."""

        listed = self.list_integrations(status="approved")
        latest_by_integration: dict[str, CatalogIntegrationRecord] = {}
        for item in listed:
            integration_name = str(item.integration_name or "").strip()
            if not integration_name:
                continue
            current = latest_by_integration.get(integration_name)
            if current is None or int(item.version) > int(current.version):
                latest_by_integration[integration_name] = item

        workspace_source_system = str(workspace_context.get("source_system") or "").strip()
        workspace_target_system = str(workspace_context.get("target_system") or "").strip()
        workspace_domain = str(workspace_context.get("business_domain") or "").strip()
        workspace_shared_concepts = {
            str(concept).strip()
            for concept in workspace_context.get("current_shared_concepts", [])
            if str(concept).strip()
        }

        candidates: list[CatalogWorkspaceReuseCandidate] = []
        for record in latest_by_integration.values():
            catalog_concepts = {str(concept).strip() for concept in record.canonical_concepts if str(concept).strip()}
            shared_concepts = sorted(workspace_shared_concepts & catalog_concepts)

            concept_overlap_score = 0.0
            if workspace_shared_concepts:
                concept_overlap_score = len(shared_concepts) / max(1, len(workspace_shared_concepts))
            elif catalog_concepts:
                concept_overlap_score = 0.2

            system_match_score = 0.0
            if workspace_source_system and workspace_target_system:
                if record.source_system == workspace_source_system and record.target_system == workspace_target_system:
                    system_match_score = 1.0
                elif record.source_system == workspace_source_system or record.target_system == workspace_target_system:
                    system_match_score = 0.5

            domain_match_score = 0.0
            if workspace_domain and record.business_domain == workspace_domain:
                domain_match_score = 1.0

            unmatched_count = len(record.unmatched_sources or [])
            decision_count = int(record.decision_count or 0)
            accepted_quality_score = 1.0 - (unmatched_count / max(1, decision_count)) if decision_count else 0.0
            accepted_quality_score = max(0.0, min(1.0, accepted_quality_score))

            score = (
                (0.35 * concept_overlap_score)
                + (0.25 * system_match_score)
                + (0.20 * domain_match_score)
                + (0.20 * accepted_quality_score)
            )

            reasons: list[str] = []
            if shared_concepts:
                reasons.append(f"Shared concepts: {', '.join(shared_concepts[:3])}")
            if system_match_score >= 1.0:
                reasons.append("Exact source-target system match")
            elif system_match_score >= 0.5:
                reasons.append("Partial source-target system match")
            if domain_match_score >= 1.0:
                reasons.append("Same business domain")
            reasons.append(f"Accepted quality proxy: {round(accepted_quality_score * 100)}%")

            candidates.append(
                CatalogWorkspaceReuseCandidate(
                    integration_name=record.integration_name,
                    mapping_set_id=record.mapping_set_id,
                    version=record.version,
                    status=record.status,
                    source_system=record.source_system,
                    target_system=record.target_system,
                    business_domain=record.business_domain,
                    artifact_type=record.artifact_type,
                    score=round(score, 4),
                    concept_overlap_score=round(concept_overlap_score, 4),
                    system_match_score=round(system_match_score, 4),
                    domain_match_score=round(domain_match_score, 4),
                    accepted_quality_score=round(accepted_quality_score, 4),
                    shared_concepts=shared_concepts,
                    reasons=reasons,
                )
            )

        candidates.sort(
            key=lambda item: (
                -float(item.score),
                -float(item.concept_overlap_score),
                -float(item.system_match_score),
                str(item.integration_name or "").lower(),
            )
        )
        limited = candidates[: max(1, int(top_n))]
        return CatalogWorkspaceReuseShortlistResponse(
            workspace_loaded=bool(workspace_context.get("workspace_loaded")),
            considered_integrations=len(latest_by_integration),
            candidates=limited,
        )

    def workspace_field_reuse_shortlist(
        self,
        *,
        workspace_context: dict,
        selected_fields: list[dict] | list[CatalogFieldReuseSelection],
        top_n: int = 5,
    ) -> CatalogFieldReuseShortlistResponse:
        """Rank approved catalog integrations against a selected subset of workspace source fields."""

        latest_by_integration: dict[str, CatalogIntegrationRecord] = {}
        for item in self.list_integrations(status="approved"):
            integration_name = str(item.integration_name or "").strip()
            if not integration_name:
                continue
            current = latest_by_integration.get(integration_name)
            if current is None or int(item.version) > int(current.version):
                latest_by_integration[integration_name] = item

        normalized_fields: list[CatalogFieldReuseSelection] = []
        seen_sources: set[str] = set()
        for raw in selected_fields:
            selection = raw if isinstance(raw, CatalogFieldReuseSelection) else CatalogFieldReuseSelection.model_validate(raw)
            source_field = str(selection.source_field or "").strip()
            if not source_field or source_field in seen_sources:
                continue
            seen_sources.add(source_field)
            normalized_fields.append(
                CatalogFieldReuseSelection(
                    source_field=source_field,
                    current_target=str(selection.current_target or "").strip() or None,
                    current_status=selection.current_status,
                )
            )

        workspace_source_system = str(workspace_context.get("source_system") or "").strip()
        workspace_target_system = str(workspace_context.get("target_system") or "").strip()
        workspace_domain = str(workspace_context.get("business_domain") or "").strip()

        candidates: list[CatalogFieldReuseCandidate] = []
        for record in latest_by_integration.values():
            detail = self._storage.get_mapping_set(int(record.mapping_set_id))
            decisions_by_source = {
                str(decision.source or "").strip(): decision
                for decision in detail.mapping_decisions
                if str(decision.source or "").strip()
            }

            matched_fields: list[CatalogFieldReuseMatch] = []
            target_match_count = 0
            for selection in normalized_fields:
                matched = decisions_by_source.get(selection.source_field)
                if matched is None:
                    continue
                current_target = str(selection.current_target or "").strip()
                matched_target = str(matched.target or "").strip() or None
                current_target_match = bool(current_target and matched_target and current_target == matched_target)
                if current_target_match:
                    target_match_count += 1
                matched_fields.append(
                    CatalogFieldReuseMatch(
                        source_field=selection.source_field,
                        target=matched_target,
                        status=matched.status,
                        transformation_present=bool(str(matched.transformation_code or "").strip()),
                        current_target_match=current_target_match,
                    )
                )

            if not matched_fields:
                continue

            source_field_overlap_score = len(matched_fields) / max(1, len(normalized_fields))
            current_target_match_score = target_match_count / max(1, len(matched_fields))

            system_match_score = 0.0
            if workspace_source_system and workspace_target_system:
                if record.source_system == workspace_source_system and record.target_system == workspace_target_system:
                    system_match_score = 1.0
                elif record.source_system == workspace_source_system or record.target_system == workspace_target_system:
                    system_match_score = 0.5

            domain_match_score = 0.0
            if workspace_domain and record.business_domain == workspace_domain:
                domain_match_score = 1.0

            unmatched_count = len(record.unmatched_sources or [])
            decision_count = int(record.decision_count or 0)
            accepted_quality_score = 1.0 - (unmatched_count / max(1, decision_count)) if decision_count else 0.0
            accepted_quality_score = max(0.0, min(1.0, accepted_quality_score))

            score = (
                (0.50 * source_field_overlap_score)
                + (0.20 * current_target_match_score)
                + (0.15 * system_match_score)
                + (0.10 * domain_match_score)
                + (0.05 * accepted_quality_score)
            )

            reasons = [f"Matched {len(matched_fields)}/{len(normalized_fields)} selected source fields."]
            matched_examples = ", ".join(item.source_field for item in matched_fields[:3])
            if matched_examples:
                reasons.append(f"Field overlap examples: {matched_examples}")
            if target_match_count:
                reasons.append(f"Current target match on {target_match_count} overlapping field(s).")
            if system_match_score >= 1.0:
                reasons.append("Exact source-target system match")
            elif system_match_score >= 0.5:
                reasons.append("Partial source-target system match")
            if domain_match_score >= 1.0:
                reasons.append("Same business domain")
            reasons.append(f"Accepted quality proxy: {round(accepted_quality_score * 100)}%")

            candidates.append(
                CatalogFieldReuseCandidate(
                    integration_name=record.integration_name,
                    mapping_set_id=record.mapping_set_id,
                    version=record.version,
                    status=record.status,
                    source_system=record.source_system,
                    target_system=record.target_system,
                    business_domain=record.business_domain,
                    artifact_type=record.artifact_type,
                    score=round(score, 4),
                    matched_field_count=len(matched_fields),
                    selected_field_count=len(normalized_fields),
                    source_field_overlap_score=round(source_field_overlap_score, 4),
                    current_target_match_score=round(current_target_match_score, 4),
                    system_match_score=round(system_match_score, 4),
                    domain_match_score=round(domain_match_score, 4),
                    accepted_quality_score=round(accepted_quality_score, 4),
                    matched_fields=matched_fields,
                    reasons=reasons,
                )
            )

        candidates.sort(
            key=lambda item: (
                -float(item.score),
                -int(item.matched_field_count),
                -float(item.current_target_match_score),
                str(item.integration_name or "").lower(),
            )
        )
        return CatalogFieldReuseShortlistResponse(
            workspace_loaded=bool(workspace_context.get("workspace_loaded")),
            selected_field_count=len(normalized_fields),
            considered_integrations=len(latest_by_integration),
            candidates=candidates[: max(1, int(top_n))],
        )


catalog_repository = CatalogRepository()

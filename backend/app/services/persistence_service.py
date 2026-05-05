from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from contextlib import contextmanager

from app.core.config import settings
from app.models.knowledge import KnowledgeAuditEntry, KnowledgeOverlayEntry, KnowledgeOverlayVersion
from app.models.mapping import (
    BenchmarkDatasetRecord,
    CatalogConceptDetail,
    CatalogConceptUsageRecord,
    CatalogIntegrationDetail,
    CatalogIntegrationRecord,
    CatalogSimilarIntegrationRecord,
    DecisionLogEntry,
    EvaluationMetrics,
    EvaluationRunRecord,
    MappingSetAuditEntry,
    MappingSetDecisionDiffEntry,
    MappingSetDiffResponse,
    MappingSetDetail,
    MappingSetRecord,
    ReusableCorrectionRule,
    TransformationTestCase,
    TransformationTestSetDetail,
    TransformationTestSetRecord,
    UserCorrectionEntry,
)


class SQLitePersistenceService:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_db(self) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reusable_correction_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mapping_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mapping_set_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mapping_catalog_entries (
                    mapping_set_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    integration_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    decision_count INTEGER NOT NULL,
                    source_dataset_id TEXT,
                    target_dataset_id TEXT,
                    source_system TEXT,
                    target_system TEXT,
                    business_domain TEXT,
                    interface_type TEXT,
                    description TEXT,
                    canonical_concepts_json TEXT NOT NULL,
                    unmatched_sources_json TEXT NOT NULL,
                    created_by TEXT,
                    owner TEXT,
                    assignee TEXT,
                    created_at TEXT,
                    FOREIGN KEY(mapping_set_id) REFERENCES mapping_sets(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mapping_catalog_integration_name ON mapping_catalog_entries (integration_name)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mapping_catalog_source_target ON mapping_catalog_entries (source_system, target_system)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mapping_catalog_status_artifact ON mapping_catalog_entries (status, artifact_type)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mapping_catalog_concepts (
                    mapping_set_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    integration_name TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    source_system TEXT,
                    target_system TEXT,
                    business_domain TEXT,
                    owner TEXT,
                    created_at TEXT,
                    PRIMARY KEY(mapping_set_id, concept_id),
                    FOREIGN KEY(mapping_set_id) REFERENCES mapping_sets(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mapping_catalog_concepts_concept ON mapping_catalog_concepts (concept_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mapping_catalog_concepts_integration ON mapping_catalog_concepts (integration_name)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transformation_test_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_overlay_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_overlay_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_id INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(version_id) REFERENCES knowledge_overlay_versions(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
        self._backfill_mapping_catalog_entries()
        self._backfill_mapping_catalog_concepts()

    def reconfigure(self, db_path: str) -> None:
        self.db_path = db_path
        self.init_db()

    def append_decision_log(self, entry: DecisionLogEntry) -> None:
        with self.connection() as connection:
            connection.execute("INSERT INTO decision_logs (payload) VALUES (?)", (entry.model_dump_json(),))

    def list_decision_logs(self) -> list[DecisionLogEntry]:
        with self.connection() as connection:
            rows = connection.execute("SELECT payload FROM decision_logs ORDER BY id ASC").fetchall()
        return [DecisionLogEntry.model_validate(json.loads(row[0])) for row in rows]

    def save_user_correction(self, entry: UserCorrectionEntry) -> UserCorrectionEntry:
        version = 1 + sum(1 for saved in self.list_user_corrections() if saved.source == entry.source)
        created_at = datetime.now(UTC).isoformat()
        payload_entry = entry.model_copy(update={"version": version, "created_at": created_at})
        with self.connection() as connection:
            cursor = connection.execute("INSERT INTO user_corrections (payload) VALUES (?)", (payload_entry.model_dump_json(),))
            correction_id = int(cursor.lastrowid)
        return payload_entry.model_copy(update={"correction_id": correction_id})

    def list_user_corrections(self) -> list[UserCorrectionEntry]:
        with self.connection() as connection:
            rows = connection.execute("SELECT id, payload FROM user_corrections ORDER BY id ASC").fetchall()
        return [
            UserCorrectionEntry.model_validate(
                {
                    **json.loads(row[1]),
                    "correction_id": int(row[0]),
                }
            )
            for row in rows
        ]

    def clear_all(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM decision_logs")
            connection.execute("DELETE FROM user_corrections")
            connection.execute("DELETE FROM reusable_correction_rules")
            connection.execute("DELETE FROM mapping_set_audit_logs")
            connection.execute("DELETE FROM mapping_catalog_concepts")
            connection.execute("DELETE FROM mapping_catalog_entries")
            connection.execute("DELETE FROM mapping_sets")
            connection.execute("DELETE FROM benchmark_datasets")
            connection.execute("DELETE FROM evaluation_runs")
            connection.execute("DELETE FROM transformation_test_sets")
            connection.execute("DELETE FROM knowledge_overlay_entries")
            connection.execute("DELETE FROM knowledge_overlay_versions")
            connection.execute("DELETE FROM knowledge_audit_logs")

    def clear_decision_logs(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM decision_logs")

    def clear_user_corrections(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM user_corrections")

    def save_mapping_set(
        self,
        name: str,
        mapping_decisions: list[dict] | list[object],
        *,
        source_dataset_id: str | None = None,
        target_dataset_id: str | None = None,
        status: str = "draft",
        integration_name: str | None = None,
        source_system: str | None = None,
        target_system: str | None = None,
        business_domain: str | None = None,
        interface_type: str | None = None,
        description: str | None = None,
        artifact_type: str | None = None,
        canonical_concepts: list[str] | None = None,
        unmatched_sources: list[str] | None = None,
        created_by: str | None = None,
        note: str | None = None,
        owner: str | None = None,
        assignee: str | None = None,
        review_note: str | None = None,
    ) -> MappingSetRecord:
        version = 1 + max(
            (record.version for record in self.list_mapping_sets() if record.name == name),
            default=0,
        )
        created_at = datetime.now(UTC).isoformat()
        serialized_decisions = [
            decision.model_dump(mode="json") if hasattr(decision, "model_dump") else dict(decision)
            for decision in mapping_decisions
        ]
        normalized_integration_name = (integration_name or name).strip() or name
        normalized_artifact_type = self._infer_artifact_type(
            artifact_type,
            target_dataset_id=target_dataset_id,
            target_system=target_system,
        )
        normalized_canonical_concepts = self._normalize_text_list(
            canonical_concepts,
            fallback=self._infer_canonical_concepts(serialized_decisions, normalized_artifact_type),
        )
        normalized_unmatched_sources = self._normalize_text_list(
            unmatched_sources,
            fallback=self._infer_unmatched_sources(serialized_decisions),
        )
        payload = json.dumps(
            {
                "status": status,
                "version": version,
                "decision_count": len(mapping_decisions),
                "source_dataset_id": source_dataset_id,
                "target_dataset_id": target_dataset_id,
                "integration_name": normalized_integration_name,
                "source_system": source_system,
                "target_system": target_system,
                "business_domain": business_domain,
                "interface_type": interface_type,
                "description": description,
                "artifact_type": normalized_artifact_type,
                "canonical_concepts": normalized_canonical_concepts,
                "unmatched_sources": normalized_unmatched_sources,
                "created_by": created_by,
                "note": note,
                "owner": owner,
                "assignee": assignee,
                "review_note": review_note,
                "created_at": created_at,
                "mapping_decisions": serialized_decisions,
            }
        )
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO mapping_sets (name, payload) VALUES (?, ?)",
                (name, payload),
            )
            mapping_set_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT OR REPLACE INTO mapping_catalog_entries (
                    mapping_set_id,
                    name,
                    integration_name,
                    version,
                    status,
                    artifact_type,
                    decision_count,
                    source_dataset_id,
                    target_dataset_id,
                    source_system,
                    target_system,
                    business_domain,
                    interface_type,
                    description,
                    canonical_concepts_json,
                    unmatched_sources_json,
                    created_by,
                    owner,
                    assignee,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping_set_id,
                    name,
                    normalized_integration_name,
                    version,
                    status,
                    normalized_artifact_type,
                    len(mapping_decisions),
                    source_dataset_id,
                    target_dataset_id,
                    source_system,
                    target_system,
                    business_domain,
                    interface_type,
                    description,
                    json.dumps(normalized_canonical_concepts),
                    json.dumps(normalized_unmatched_sources),
                    created_by,
                    owner,
                    assignee,
                    created_at,
                ),
            )
            self._replace_catalog_concepts(
                connection,
                mapping_set_id=mapping_set_id,
                name=name,
                integration_name=normalized_integration_name,
                version=version,
                status=status,
                artifact_type=normalized_artifact_type,
                source_system=source_system,
                target_system=target_system,
                business_domain=business_domain,
                owner=owner,
                created_at=created_at,
                canonical_concepts=normalized_canonical_concepts,
            )
        return MappingSetRecord(
            mapping_set_id=mapping_set_id,
            name=name,
            status=status,
            version=version,
            decision_count=len(mapping_decisions),
            source_dataset_id=source_dataset_id,
            target_dataset_id=target_dataset_id,
            integration_name=normalized_integration_name,
            source_system=source_system,
            target_system=target_system,
            business_domain=business_domain,
            interface_type=interface_type,
            description=description,
            artifact_type=normalized_artifact_type,
            canonical_concepts=normalized_canonical_concepts,
            unmatched_sources=normalized_unmatched_sources,
            created_by=created_by,
            note=note,
            owner=owner,
            assignee=assignee,
            review_note=review_note,
            created_at=created_at,
        )

    def list_mapping_sets(self) -> list[MappingSetRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, name, payload FROM mapping_sets ORDER BY id DESC"
            ).fetchall()
        records: list[MappingSetRecord] = []
        for row in rows:
            payload = json.loads(row[2])
            records.append(
                MappingSetRecord(
                    mapping_set_id=int(row[0]),
                    name=row[1],
                    status=payload.get("status", "draft"),
                    version=payload.get("version", 1),
                    decision_count=payload.get("decision_count", len(payload.get("mapping_decisions", []))),
                    source_dataset_id=payload.get("source_dataset_id"),
                    target_dataset_id=payload.get("target_dataset_id"),
                    integration_name=payload.get("integration_name", row[1]),
                    source_system=payload.get("source_system"),
                    target_system=payload.get("target_system"),
                    business_domain=payload.get("business_domain"),
                    interface_type=payload.get("interface_type"),
                    description=payload.get("description"),
                    artifact_type=payload.get(
                        "artifact_type",
                        self._infer_artifact_type(
                            None,
                            target_dataset_id=payload.get("target_dataset_id"),
                            target_system=payload.get("target_system"),
                        ),
                    ),
                    canonical_concepts=self._normalize_text_list(payload.get("canonical_concepts")),
                    unmatched_sources=self._normalize_text_list(
                        payload.get("unmatched_sources"),
                        fallback=self._infer_unmatched_sources(payload.get("mapping_decisions", [])),
                    ),
                    created_by=payload.get("created_by"),
                    note=payload.get("note"),
                    owner=payload.get("owner"),
                    assignee=payload.get("assignee"),
                    review_note=payload.get("review_note"),
                    created_at=payload.get("created_at"),
                )
            )
        return records

    def get_mapping_set(self, mapping_set_id: int) -> MappingSetDetail:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, name, payload FROM mapping_sets WHERE id = ?",
                (mapping_set_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown mapping set id: {mapping_set_id}")
        payload = json.loads(row[2])
        return MappingSetDetail(
            mapping_set_id=int(row[0]),
            name=row[1],
            status=payload.get("status", "draft"),
            version=payload.get("version", 1),
            decision_count=payload.get("decision_count", len(payload.get("mapping_decisions", []))),
            source_dataset_id=payload.get("source_dataset_id"),
            target_dataset_id=payload.get("target_dataset_id"),
            integration_name=payload.get("integration_name", row[1]),
            source_system=payload.get("source_system"),
            target_system=payload.get("target_system"),
            business_domain=payload.get("business_domain"),
            interface_type=payload.get("interface_type"),
            description=payload.get("description"),
            artifact_type=payload.get(
                "artifact_type",
                self._infer_artifact_type(
                    None,
                    target_dataset_id=payload.get("target_dataset_id"),
                    target_system=payload.get("target_system"),
                ),
            ),
            canonical_concepts=self._normalize_text_list(payload.get("canonical_concepts")),
            unmatched_sources=self._normalize_text_list(
                payload.get("unmatched_sources"),
                fallback=self._infer_unmatched_sources(payload.get("mapping_decisions", [])),
            ),
            created_by=payload.get("created_by"),
            note=payload.get("note"),
            owner=payload.get("owner"),
            assignee=payload.get("assignee"),
            review_note=payload.get("review_note"),
            created_at=payload.get("created_at"),
            mapping_decisions=payload.get("mapping_decisions", []),
        )

    def update_mapping_set_status(
        self,
        mapping_set_id: int,
        status: str,
        *,
        owner: str | None = None,
        assignee: str | None = None,
        review_note: str | None = None,
    ) -> MappingSetRecord:
        existing = self.get_mapping_set(mapping_set_id)
        payload = existing.model_dump(mode="json")
        payload["status"] = status
        if owner is not None:
            payload["owner"] = owner
        if assignee is not None:
            payload["assignee"] = assignee
        if review_note is not None:
            payload["review_note"] = review_note
        payload.pop("mapping_set_id", None)
        with self.connection() as connection:
            connection.execute(
                "UPDATE mapping_sets SET payload = ? WHERE id = ?",
                (json.dumps(payload), mapping_set_id),
            )
            connection.execute(
                "UPDATE mapping_catalog_entries SET status = ?, owner = ?, assignee = ? WHERE mapping_set_id = ?",
                (
                    status,
                    payload.get("owner"),
                    payload.get("assignee"),
                    mapping_set_id,
                ),
            )
            connection.execute(
                "UPDATE mapping_catalog_concepts SET status = ?, owner = ? WHERE mapping_set_id = ?",
                (
                    status,
                    payload.get("owner"),
                    mapping_set_id,
                ),
            )
        return existing.model_copy(
            update={
                "status": status,
                "owner": payload.get("owner"),
                "assignee": payload.get("assignee"),
                "review_note": payload.get("review_note"),
            }
        )

    def list_catalog_integrations(
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
        query = (
            "SELECT mapping_set_id, name, integration_name, version, status, artifact_type, decision_count, "
            "source_dataset_id, target_dataset_id, source_system, target_system, business_domain, interface_type, "
            "description, canonical_concepts_json, unmatched_sources_json, created_by, owner, assignee, created_at "
            "FROM mapping_catalog_entries"
        )
        clauses: list[str] = []
        params: list[object] = []
        if source_system:
            clauses.append("source_system = ?")
            params.append(source_system)
        if target_system:
            clauses.append("target_system = ?")
            params.append(target_system)
        if business_domain:
            clauses.append("business_domain = ?")
            params.append(business_domain)
        if owner:
            clauses.append("owner = ?")
            params.append(owner)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if artifact_type:
            clauses.append("artifact_type = ?")
            params.append(artifact_type)
        if integration_name:
            clauses.append("integration_name LIKE ?")
            params.append(f"%{integration_name}%")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY integration_name ASC, version DESC, mapping_set_id DESC"

        with self.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [
            self._catalog_record_from_row(row)
            for row in rows
        ]

    def search_catalog_integrations(
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
        normalized_query = str(query_text or "").strip()
        if not normalized_query:
            return self.list_catalog_integrations(
                source_system=source_system,
                target_system=target_system,
                business_domain=business_domain,
                owner=owner,
                status=status,
                artifact_type=artifact_type,
            )

        search_like = f"%{normalized_query}%"
        query = (
            "SELECT mapping_set_id, name, integration_name, version, status, artifact_type, decision_count, "
            "source_dataset_id, target_dataset_id, source_system, target_system, business_domain, interface_type, "
            "description, canonical_concepts_json, unmatched_sources_json, created_by, owner, assignee, created_at "
            "FROM mapping_catalog_entries WHERE ("
            "integration_name LIKE ? OR name LIKE ? OR COALESCE(source_system, '') LIKE ? OR COALESCE(target_system, '') LIKE ? "
            "OR COALESCE(business_domain, '') LIKE ? OR COALESCE(interface_type, '') LIKE ? OR COALESCE(owner, '') LIKE ? "
            "OR mapping_set_id IN (SELECT mapping_set_id FROM mapping_catalog_concepts WHERE concept_id LIKE ?))"
        )
        params: list[object] = [
            search_like,
            search_like,
            search_like,
            search_like,
            search_like,
            search_like,
            search_like,
            search_like,
        ]
        if source_system:
            query += " AND source_system = ?"
            params.append(source_system)
        if target_system:
            query += " AND target_system = ?"
            params.append(target_system)
        if business_domain:
            query += " AND business_domain = ?"
            params.append(business_domain)
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        if status:
            query += " AND status = ?"
            params.append(status)
        if artifact_type:
            query += " AND artifact_type = ?"
            params.append(artifact_type)
        query += " ORDER BY integration_name ASC, version DESC, mapping_set_id DESC"

        with self.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._catalog_record_from_row(row) for row in rows]

    def get_catalog_integration_detail(self, integration_name: str) -> CatalogIntegrationDetail:
        records = self.list_catalog_integrations(integration_name=integration_name)
        exact_matches = [record for record in records if record.integration_name == integration_name]
        if not exact_matches:
            raise KeyError(f"Unknown catalog integration: {integration_name}")
        latest_version = exact_matches[0]
        latest_approved_version = next((record for record in exact_matches if record.status == "approved"), None)
        canonical_concepts = self._normalize_text_list(
            [concept for record in exact_matches for concept in record.canonical_concepts]
        )
        unmatched_sources = self._normalize_text_list(
            [source for record in exact_matches for source in record.unmatched_sources]
        )
        similar_integrations = self._list_similar_catalog_integrations(
            integration_name=integration_name,
            latest_version=latest_version,
            latest_approved_version=latest_approved_version,
            canonical_concepts=canonical_concepts,
        )
        return CatalogIntegrationDetail(
            integration_name=integration_name,
            source_system=latest_version.source_system,
            target_system=latest_version.target_system,
            business_domain=latest_version.business_domain,
            interface_type=latest_version.interface_type,
            description=latest_version.description,
            canonical_concepts=canonical_concepts,
            unmatched_sources=unmatched_sources,
            latest_version=latest_version,
            latest_approved_version=latest_approved_version,
            versions=exact_matches,
            similar_integrations=similar_integrations,
        )

    def get_catalog_concept_detail(
        self,
        concept_id: str,
        *,
        source_system: str | None = None,
        target_system: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> CatalogConceptDetail:
        query = (
            "SELECT concept_id, mapping_set_id, name, integration_name, version, status, artifact_type, "
            "source_system, target_system, business_domain, owner, created_at "
            "FROM mapping_catalog_concepts WHERE concept_id = ?"
        )
        params: list[object] = [concept_id]
        if source_system:
            query += " AND source_system = ?"
            params.append(source_system)
        if target_system:
            query += " AND target_system = ?"
            params.append(target_system)
        if status:
            query += " AND status = ?"
            params.append(status)
        if artifact_type:
            query += " AND artifact_type = ?"
            params.append(artifact_type)
        query += " ORDER BY integration_name ASC, version DESC, mapping_set_id DESC"

        with self.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        if not rows:
            raise KeyError(f"Unknown catalog concept: {concept_id}")
        integrations = [
            CatalogConceptUsageRecord(
                concept_id=row[0],
                mapping_set_id=int(row[1]),
                name=row[2],
                integration_name=row[3],
                version=int(row[4]),
                status=row[5],
                artifact_type=row[6],
                source_system=row[7],
                target_system=row[8],
                business_domain=row[9],
                owner=row[10],
                created_at=row[11],
            )
            for row in rows
        ]
        return CatalogConceptDetail(
            concept_id=concept_id,
            usage_count=len(integrations),
            integrations=integrations,
        )

    def append_mapping_set_audit_log(self, entry: MappingSetAuditEntry | dict[str, object]) -> MappingSetAuditEntry:
        payload_entry = entry if isinstance(entry, MappingSetAuditEntry) else MappingSetAuditEntry.model_validate(entry)
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO mapping_set_audit_logs (payload) VALUES (?)",
                (payload_entry.model_dump_json(exclude={"audit_id"}),),
            )
            audit_id = int(cursor.lastrowid)
        return payload_entry.model_copy(update={"audit_id": audit_id})

    def list_mapping_set_audit_logs(self, mapping_set_id: int | None = None) -> list[MappingSetAuditEntry]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, payload FROM mapping_set_audit_logs ORDER BY id DESC"
            ).fetchall()
        entries = [MappingSetAuditEntry.model_validate({**json.loads(row[1]), "audit_id": int(row[0])}) for row in rows]
        if mapping_set_id is None:
            return entries
        return [entry for entry in entries if entry.mapping_set_id == mapping_set_id]

    def diff_mapping_sets(self, mapping_set_id: int, against_mapping_set_id: int) -> MappingSetDiffResponse:
        current = self.get_mapping_set(mapping_set_id)
        baseline = self.get_mapping_set(against_mapping_set_id)
        if current.name != baseline.name:
            raise ValueError("Mapping set diff requires two versions with the same name")

        def as_dict(decision: object) -> dict[str, object]:
            if hasattr(decision, "model_dump"):
                return decision.model_dump(mode="json")
            return dict(decision)

        current_by_source = {item["source"]: item for item in (as_dict(decision) for decision in current.mapping_decisions)}
        baseline_by_source = {item["source"]: item for item in (as_dict(decision) for decision in baseline.mapping_decisions)}
        changes: list[MappingSetDecisionDiffEntry] = []

        for source in sorted(set(current_by_source) | set(baseline_by_source)):
            current_decision = current_by_source.get(source)
            baseline_decision = baseline_by_source.get(source)
            if baseline_decision is None and current_decision is not None:
                changes.append(
                    MappingSetDecisionDiffEntry(
                        change_type="added",
                        source=source,
                        to_target=current_decision.get("target"),
                        to_status=current_decision.get("status"),
                        to_transformation_code=current_decision.get("transformation_code"),
                    )
                )
                continue
            if current_decision is None and baseline_decision is not None:
                changes.append(
                    MappingSetDecisionDiffEntry(
                        change_type="removed",
                        source=source,
                        from_target=baseline_decision.get("target"),
                        from_status=baseline_decision.get("status"),
                        from_transformation_code=baseline_decision.get("transformation_code"),
                    )
                )
                continue
            if current_decision is None or baseline_decision is None:
                continue
            if (
                current_decision.get("target") != baseline_decision.get("target")
                or current_decision.get("status") != baseline_decision.get("status")
                or current_decision.get("transformation_code") != baseline_decision.get("transformation_code")
            ):
                changes.append(
                    MappingSetDecisionDiffEntry(
                        change_type="changed",
                        source=source,
                        from_target=baseline_decision.get("target"),
                        to_target=current_decision.get("target"),
                        from_status=baseline_decision.get("status"),
                        to_status=current_decision.get("status"),
                        from_transformation_code=baseline_decision.get("transformation_code"),
                        to_transformation_code=current_decision.get("transformation_code"),
                    )
                )

        return MappingSetDiffResponse(
            current_mapping_set_id=current.mapping_set_id,
            current_name=current.name,
            current_version=current.version,
            against_mapping_set_id=baseline.mapping_set_id,
            against_name=baseline.name,
            against_version=baseline.version,
            added_count=sum(1 for item in changes if item.change_type == "added"),
            removed_count=sum(1 for item in changes if item.change_type == "removed"),
            changed_count=sum(1 for item in changes if item.change_type == "changed"),
            changes=changes,
        )

    def clear_mapping_sets(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM mapping_set_audit_logs")
            connection.execute("DELETE FROM mapping_catalog_concepts")
            connection.execute("DELETE FROM mapping_catalog_entries")
            connection.execute("DELETE FROM mapping_sets")

    def _catalog_record_from_row(self, row: sqlite3.Row | tuple[object, ...]) -> CatalogIntegrationRecord:
        return CatalogIntegrationRecord(
            mapping_set_id=int(row[0]),
            name=row[1],
            integration_name=row[2],
            version=int(row[3]),
            status=row[4],
            artifact_type=row[5],
            decision_count=int(row[6]),
            source_dataset_id=row[7],
            target_dataset_id=row[8],
            source_system=row[9],
            target_system=row[10],
            business_domain=row[11],
            interface_type=row[12],
            description=row[13],
            canonical_concepts=json.loads(row[14] or "[]"),
            unmatched_sources=json.loads(row[15] or "[]"),
            created_by=row[16],
            owner=row[17],
            assignee=row[18],
            created_at=row[19],
        )

    def _list_similar_catalog_integrations(
        self,
        *,
        integration_name: str,
        latest_version: CatalogIntegrationRecord,
        latest_approved_version: CatalogIntegrationRecord | None,
        canonical_concepts: list[str],
    ) -> list[CatalogSimilarIntegrationRecord]:
        reference_concepts = set(self._normalize_text_list(canonical_concepts))
        if not reference_concepts:
            return []

        grouped_records: dict[str, list[CatalogIntegrationRecord]] = {}
        for record in self.list_catalog_integrations():
            if record.integration_name == integration_name:
                continue
            grouped_records.setdefault(record.integration_name, []).append(record)

        similarities: list[CatalogSimilarIntegrationRecord] = []
        for candidate_name, candidate_records in grouped_records.items():
            candidate_latest_version = candidate_records[0]
            candidate_latest_approved = next(
                (record for record in candidate_records if record.status == "approved"),
                None,
            )
            candidate_concepts = self._normalize_text_list(
                concept
                for record in candidate_records
                for concept in record.canonical_concepts
                if concept in reference_concepts
            )
            if not candidate_concepts:
                continue

            same_source_system = bool(latest_version.source_system) and (
                candidate_latest_version.source_system == latest_version.source_system
            )
            same_target_system = bool(latest_version.target_system) and (
                candidate_latest_version.target_system == latest_version.target_system
            )
            same_business_domain = bool(latest_version.business_domain) and (
                candidate_latest_version.business_domain == latest_version.business_domain
            )
            same_artifact_type = candidate_latest_version.artifact_type == latest_version.artifact_type

            max_score = (len(reference_concepts) * 3) + 4
            weighted_score = (len(candidate_concepts) * 3)
            weighted_score += int(same_source_system)
            weighted_score += int(same_target_system)
            weighted_score += int(same_business_domain)
            weighted_score += int(same_artifact_type)

            similarities.append(
                CatalogSimilarIntegrationRecord(
                    integration_name=candidate_name,
                    similarity_score=round(weighted_score / max_score, 3),
                    shared_concepts=candidate_concepts,
                    shared_concept_count=len(candidate_concepts),
                    same_source_system=same_source_system,
                    same_target_system=same_target_system,
                    same_business_domain=same_business_domain,
                    same_artifact_type=same_artifact_type,
                    latest_version=candidate_latest_version,
                    latest_approved_version=candidate_latest_approved,
                )
            )

        similarities.sort(
            key=lambda item: (
                -item.similarity_score,
                -item.shared_concept_count,
                item.integration_name.lower(),
            )
        )
        return similarities

    def _replace_catalog_concepts(
        self,
        connection: sqlite3.Connection,
        *,
        mapping_set_id: int,
        name: str,
        integration_name: str,
        version: int,
        status: str,
        artifact_type: str,
        source_system: str | None,
        target_system: str | None,
        business_domain: str | None,
        owner: str | None,
        created_at: str | None,
        canonical_concepts: list[str],
    ) -> None:
        connection.execute("DELETE FROM mapping_catalog_concepts WHERE mapping_set_id = ?", (mapping_set_id,))
        for concept_id in canonical_concepts:
            connection.execute(
                """
                INSERT OR REPLACE INTO mapping_catalog_concepts (
                    mapping_set_id,
                    name,
                    integration_name,
                    concept_id,
                    version,
                    status,
                    artifact_type,
                    source_system,
                    target_system,
                    business_domain,
                    owner,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping_set_id,
                    name,
                    integration_name,
                    concept_id,
                    version,
                    status,
                    artifact_type,
                    source_system,
                    target_system,
                    business_domain,
                    owner,
                    created_at,
                ),
            )

    def _normalize_text_list(
        self,
        values: list[object] | tuple[object, ...] | None,
        *,
        fallback: list[str] | None = None,
    ) -> list[str]:
        source_values = values if values is not None else fallback or []
        normalized: list[str] = []
        seen: set[str] = set()
        for value in source_values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def _infer_artifact_type(
        self,
        artifact_type: str | None,
        *,
        target_dataset_id: str | None,
        target_system: str | None,
    ) -> str:
        normalized = str(artifact_type or "").strip().lower()
        normalized_target_system = str(target_system or "").strip().lower()
        has_target_dataset = bool(str(target_dataset_id or "").strip())
        points_to_canonical = not normalized_target_system or normalized_target_system.startswith("canonical")

        if normalized in {"standard", "canonical-only"}:
            return normalized
        if has_target_dataset:
            return "standard"
        if normalized_target_system and not points_to_canonical:
            return "standard"
        if not target_dataset_id and points_to_canonical:
            return "canonical-only"
        return "standard"

    def _infer_canonical_concepts(self, mapping_decisions: list[dict[str, object]], artifact_type: str) -> list[str]:
        if artifact_type != "canonical-only":
            return []
        return self._normalize_text_list(decision.get("target") for decision in mapping_decisions)

    def _infer_unmatched_sources(self, mapping_decisions: list[dict[str, object]] | list[object]) -> list[str]:
        unmatched: list[str] = []
        seen: set[str] = set()
        for raw_decision in mapping_decisions:
            decision = raw_decision if isinstance(raw_decision, dict) else dict(raw_decision)
            source = str(decision.get("source") or "").strip()
            target = str(decision.get("target") or "").strip()
            if source and not target and source not in seen:
                seen.add(source)
                unmatched.append(source)
        return unmatched

    def _backfill_mapping_catalog_entries(self) -> None:
        mapping_sets = self.list_mapping_sets()
        if not mapping_sets:
            return
        with self.connection() as connection:
            existing_ids = {
                int(row[0])
                for row in connection.execute("SELECT mapping_set_id FROM mapping_catalog_entries").fetchall()
            }
            for record in mapping_sets:
                if record.mapping_set_id in existing_ids:
                    continue
                detail = self.get_mapping_set(record.mapping_set_id)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO mapping_catalog_entries (
                        mapping_set_id,
                        name,
                        integration_name,
                        version,
                        status,
                        artifact_type,
                        decision_count,
                        source_dataset_id,
                        target_dataset_id,
                        source_system,
                        target_system,
                        business_domain,
                        interface_type,
                        description,
                        canonical_concepts_json,
                        unmatched_sources_json,
                        created_by,
                        owner,
                        assignee,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        detail.mapping_set_id,
                        detail.name,
                        detail.integration_name or detail.name,
                        detail.version,
                        detail.status,
                        detail.artifact_type,
                        detail.decision_count,
                        detail.source_dataset_id,
                        detail.target_dataset_id,
                        detail.source_system,
                        detail.target_system,
                        detail.business_domain,
                        detail.interface_type,
                        detail.description,
                        json.dumps(detail.canonical_concepts),
                        json.dumps(detail.unmatched_sources),
                        detail.created_by,
                        detail.owner,
                        detail.assignee,
                        detail.created_at,
                    ),
                )

    def _backfill_mapping_catalog_concepts(self) -> None:
        with self.connection() as connection:
            concept_ids_by_mapping_set: dict[int, int] = {
                int(row[0]): int(row[1])
                for row in connection.execute(
                    "SELECT mapping_set_id, COUNT(*) FROM mapping_catalog_concepts GROUP BY mapping_set_id"
                ).fetchall()
            }
            rows = connection.execute(
                "SELECT mapping_set_id, name, integration_name, version, status, artifact_type, "
                "source_system, target_system, business_domain, owner, created_at, canonical_concepts_json "
                "FROM mapping_catalog_entries"
            ).fetchall()
            for row in rows:
                mapping_set_id = int(row[0])
                if concept_ids_by_mapping_set.get(mapping_set_id, 0) > 0:
                    continue
                self._replace_catalog_concepts(
                    connection,
                    mapping_set_id=mapping_set_id,
                    name=row[1],
                    integration_name=row[2],
                    version=int(row[3]),
                    status=row[4],
                    artifact_type=row[5],
                    source_system=row[6],
                    target_system=row[7],
                    business_domain=row[8],
                    owner=row[9],
                    created_at=row[10],
                    canonical_concepts=self._normalize_text_list(json.loads(row[11] or "[]")),
                )

    def save_reusable_correction_rule(self, rule: ReusableCorrectionRule | dict[str, object]) -> ReusableCorrectionRule:
        payload_model = rule if isinstance(rule, ReusableCorrectionRule) else ReusableCorrectionRule.model_validate(rule)
        existing = next(
            (
                item
                for item in self.list_reusable_correction_rules(include_inactive=True)
                if item.source == payload_model.source
                and item.suggested_target == payload_model.suggested_target
                and item.corrected_target == payload_model.corrected_target
                and item.status == payload_model.status
                and item.active
            ),
            None,
        )

        if existing is not None and existing.rule_id is not None:
            updated = existing.model_copy(
                update={
                    "occurrence_count": max(existing.occurrence_count, payload_model.occurrence_count),
                    "created_by": existing.created_by or payload_model.created_by,
                    "note": existing.note or payload_model.note,
                }
            )
            payload = updated.model_dump(mode="json")
            payload.pop("rule_id", None)
            with self.connection() as connection:
                connection.execute(
                    "UPDATE reusable_correction_rules SET payload = ? WHERE id = ?",
                    (json.dumps(payload), existing.rule_id),
                )
            return updated

        created_at = datetime.now(UTC).isoformat()
        payload_entry = payload_model.model_copy(update={"created_at": payload_model.created_at or created_at})
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO reusable_correction_rules (payload) VALUES (?)",
                (payload_entry.model_dump_json(exclude={"rule_id"}),),
            )
            rule_id = int(cursor.lastrowid)
        return payload_entry.model_copy(update={"rule_id": rule_id})

    def list_reusable_correction_rules(self, *, include_inactive: bool = False) -> list[ReusableCorrectionRule]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, payload FROM reusable_correction_rules ORDER BY id ASC"
            ).fetchall()
        rules = [ReusableCorrectionRule.model_validate({**json.loads(row[1]), "rule_id": int(row[0])}) for row in rows]
        if include_inactive:
            return rules
        return [rule for rule in rules if rule.active]

    def clear_reusable_correction_rules(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM reusable_correction_rules")

    def save_benchmark_dataset(self, name: str, cases: list[dict]) -> BenchmarkDatasetRecord:
        version = 1 + max(
            (record.version for record in self.list_benchmark_datasets() if record.name == name),
            default=0,
        )
        created_at = datetime.now(UTC).isoformat()
        payload = json.dumps(
            {
                "cases": cases,
                "version": version,
                "created_at": created_at,
                "case_count": len(cases),
            }
        )
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO benchmark_datasets (name, payload) VALUES (?, ?)",
                (name, payload),
            )
            dataset_id = int(cursor.lastrowid)
        return BenchmarkDatasetRecord(
            dataset_id=dataset_id,
            name=name,
            case_count=len(cases),
            version=version,
            created_at=created_at,
        )

    def list_benchmark_datasets(self) -> list[BenchmarkDatasetRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, name, payload FROM benchmark_datasets ORDER BY id ASC"
            ).fetchall()
        records: list[BenchmarkDatasetRecord] = []
        for row in rows:
            payload = json.loads(row[2])
            records.append(
                BenchmarkDatasetRecord(
                    dataset_id=int(row[0]),
                    name=row[1],
                    case_count=payload.get("case_count", len(payload.get("cases", []))),
                    version=payload.get("version", 1),
                    created_at=payload.get("created_at"),
                )
            )
        return records

    def get_benchmark_dataset_cases(self, dataset_id: int) -> list[dict]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM benchmark_datasets WHERE id = ?",
                (dataset_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown benchmark dataset id: {dataset_id}")
        payload = json.loads(row[0])
        return payload.get("cases", payload)

    def clear_benchmark_datasets(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM benchmark_datasets")

    def save_evaluation_run(
        self,
        dataset_id: int | None,
        dataset_name: str | None,
        provider_name: str,
        metrics: EvaluationMetrics,
    ) -> EvaluationRunRecord:
        created_at = datetime.now(UTC).isoformat()
        payload = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "provider_name": provider_name,
            "total_cases": metrics.total_cases,
            "total_fields": metrics.total_fields,
            "correct_matches": metrics.correct_matches,
            "top1_accuracy": metrics.top1_accuracy,
            "accuracy": metrics.accuracy,
            "confidence_by_bucket": metrics.confidence_by_bucket,
            "created_at": created_at,
        }
        with self.connection() as connection:
            cursor = connection.execute("INSERT INTO evaluation_runs (payload) VALUES (?)", (json.dumps(payload),))
            run_id = int(cursor.lastrowid)
        return EvaluationRunRecord(run_id=run_id, **payload)

    def list_evaluation_runs(self) -> list[EvaluationRunRecord]:
        with self.connection() as connection:
            rows = connection.execute("SELECT id, payload FROM evaluation_runs ORDER BY id DESC").fetchall()
        return [EvaluationRunRecord(run_id=int(row[0]), **json.loads(row[1])) for row in rows]

    def clear_evaluation_runs(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM evaluation_runs")

    def save_transformation_test_set(
        self,
        name: str,
        mapping_decisions: list[dict] | list[object],
        cases: list[TransformationTestCase | dict[str, object]],
    ) -> TransformationTestSetRecord:
        version = 1 + max(
            (record.version for record in self.list_transformation_test_sets() if record.name == name),
            default=0,
        )
        created_at = datetime.now(UTC).isoformat()
        payload = json.dumps(
            {
                "mapping_decisions": [
                    decision.model_dump(mode="json") if hasattr(decision, "model_dump") else decision
                    for decision in mapping_decisions
                ],
                "cases": [
                    case.model_dump(mode="json") if isinstance(case, TransformationTestCase) else case
                    for case in cases
                ],
                "version": version,
                "created_at": created_at,
                "mapping_count": len(mapping_decisions),
                "case_count": len(cases),
            }
        )
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO transformation_test_sets (name, payload) VALUES (?, ?)",
                (name, payload),
            )
            test_set_id = int(cursor.lastrowid)
        return TransformationTestSetRecord(
            test_set_id=test_set_id,
            name=name,
            mapping_count=len(mapping_decisions),
            case_count=len(cases),
            version=version,
            created_at=created_at,
        )

    def list_transformation_test_sets(self) -> list[TransformationTestSetRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, name, payload FROM transformation_test_sets ORDER BY id ASC"
            ).fetchall()
        records: list[TransformationTestSetRecord] = []
        for row in rows:
            payload = json.loads(row[2])
            records.append(
                TransformationTestSetRecord(
                    test_set_id=int(row[0]),
                    name=row[1],
                    mapping_count=payload.get("mapping_count", len(payload.get("mapping_decisions", []))),
                    case_count=payload.get("case_count", len(payload.get("cases", []))),
                    version=payload.get("version", 1),
                    created_at=payload.get("created_at"),
                )
            )
        return records

    def get_transformation_test_set(self, test_set_id: int) -> TransformationTestSetDetail:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, name, payload FROM transformation_test_sets WHERE id = ?",
                (test_set_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown transformation test set id: {test_set_id}")
        payload = json.loads(row[2])
        return TransformationTestSetDetail(
            test_set_id=int(row[0]),
            name=row[1],
            mapping_count=payload.get("mapping_count", len(payload.get("mapping_decisions", []))),
            case_count=payload.get("case_count", len(payload.get("cases", []))),
            version=payload.get("version", 1),
            created_at=payload.get("created_at"),
            mapping_decisions=payload.get("mapping_decisions", []),
            cases=payload.get("cases", []),
        )

    def clear_transformation_test_sets(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM transformation_test_sets")

    def append_knowledge_audit_log(self, entry: KnowledgeAuditEntry) -> KnowledgeAuditEntry:
        with self.connection() as connection:
            cursor = connection.execute("INSERT INTO knowledge_audit_logs (payload) VALUES (?)", (entry.model_dump_json(exclude={"audit_id"}),))
            audit_id = int(cursor.lastrowid)
        return entry.model_copy(update={"audit_id": audit_id})

    def list_knowledge_audit_logs(self) -> list[KnowledgeAuditEntry]:
        with self.connection() as connection:
            rows = connection.execute("SELECT id, payload FROM knowledge_audit_logs ORDER BY id DESC").fetchall()
        return [KnowledgeAuditEntry.model_validate({**json.loads(row[1]), "audit_id": int(row[0])}) for row in rows]

    def clear_knowledge_audit_logs(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM knowledge_audit_logs")

    def save_knowledge_overlay_version(
        self,
        name: str,
        *,
        status: str = "draft",
        scope: str = "global",
        created_by: str | None = None,
        source_filename: str | None = None,
    ) -> KnowledgeOverlayVersion:
        created_at = datetime.now(UTC).isoformat()
        payload = KnowledgeOverlayVersion(
            name=name,
            status=status,
            scope=scope,
            created_by=created_by,
            source_filename=source_filename,
            created_at=created_at,
        )
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO knowledge_overlay_versions (payload) VALUES (?)",
                (payload.model_dump_json(exclude={"overlay_id"}),),
            )
            overlay_id = int(cursor.lastrowid)
        return payload.model_copy(update={"overlay_id": overlay_id})

    def save_knowledge_overlay_entries(
        self,
        overlay_id: int,
        entries: list[KnowledgeOverlayEntry | dict[str, object]],
    ) -> list[KnowledgeOverlayEntry]:
        saved_entries: list[KnowledgeOverlayEntry] = []
        with self.connection() as connection:
            for entry in entries:
                payload_model = entry if isinstance(entry, KnowledgeOverlayEntry) else KnowledgeOverlayEntry.model_validate(entry)
                payload_entry = payload_model.model_copy(update={"version_id": overlay_id})
                cursor = connection.execute(
                    "INSERT INTO knowledge_overlay_entries (version_id, payload) VALUES (?, ?)",
                    (overlay_id, payload_entry.model_dump_json(exclude={"entry_id"})),
                )
                saved_entries.append(payload_entry.model_copy(update={"entry_id": int(cursor.lastrowid)}))
        return saved_entries

    def list_knowledge_overlay_versions(self) -> list[KnowledgeOverlayVersion]:
        with self.connection() as connection:
            rows = connection.execute("SELECT id, payload FROM knowledge_overlay_versions ORDER BY id ASC").fetchall()
        return [KnowledgeOverlayVersion.model_validate({**json.loads(row[1]), "overlay_id": int(row[0])}) for row in rows]

    def get_knowledge_overlay_version(self, overlay_id: int) -> KnowledgeOverlayVersion:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, payload FROM knowledge_overlay_versions WHERE id = ?",
                (overlay_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown knowledge overlay version id: {overlay_id}")
        return KnowledgeOverlayVersion.model_validate({**json.loads(row[1]), "overlay_id": int(row[0])})

    def get_knowledge_overlay_entries(self, overlay_id: int) -> list[KnowledgeOverlayEntry]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, payload FROM knowledge_overlay_entries WHERE version_id = ? ORDER BY id ASC",
                (overlay_id,),
            ).fetchall()
        return [KnowledgeOverlayEntry.model_validate({**json.loads(row[1]), "entry_id": int(row[0])}) for row in rows]

    def get_active_knowledge_overlay_version(self) -> KnowledgeOverlayVersion | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, payload FROM knowledge_overlay_versions ORDER BY id ASC"
            ).fetchall()
        active_rows = [record for record in row if json.loads(record[1]).get("status") == "active"]
        if not active_rows:
            return None
        latest_active = active_rows[-1]
        return KnowledgeOverlayVersion.model_validate({**json.loads(latest_active[1]), "overlay_id": int(latest_active[0])})

    def activate_knowledge_overlay_version(self, overlay_id: int) -> KnowledgeOverlayVersion:
        target = self.get_knowledge_overlay_version(overlay_id)
        activated_at = datetime.now(UTC).isoformat()
        with self.connection() as connection:
            rows = connection.execute("SELECT id, payload FROM knowledge_overlay_versions ORDER BY id ASC").fetchall()
            for row in rows:
                row_id = int(row[0])
                payload = json.loads(row[1])
                if row_id == overlay_id:
                    payload["status"] = "active"
                    payload["activated_at"] = activated_at
                elif payload.get("status") == "active":
                    payload["status"] = "validated"
                    payload["activated_at"] = None
                connection.execute(
                    "UPDATE knowledge_overlay_versions SET payload = ? WHERE id = ?",
                    (json.dumps(payload), row_id),
                )
        return target.model_copy(update={"status": "active", "activated_at": activated_at})

    def deactivate_knowledge_overlay_version(self, overlay_id: int) -> KnowledgeOverlayVersion:
        target = self.get_knowledge_overlay_version(overlay_id)
        if target.status != "active":
            return target

        payload = target.model_dump(mode="json")
        payload["status"] = "validated"
        payload["activated_at"] = None
        payload.pop("overlay_id", None)
        with self.connection() as connection:
            connection.execute(
                "UPDATE knowledge_overlay_versions SET payload = ? WHERE id = ?",
                (json.dumps(payload), overlay_id),
            )
        return target.model_copy(update={"status": "validated", "activated_at": None})

    def rollback_knowledge_overlay_version(self) -> KnowledgeOverlayVersion | None:
        active_version = self.get_active_knowledge_overlay_version()
        if active_version is None or active_version.overlay_id is None:
            raise KeyError("No active knowledge overlay version to roll back.")

        versions = self.list_knowledge_overlay_versions()
        rollback_candidates = [
            version
            for version in versions
            if version.overlay_id != active_version.overlay_id and version.status == "validated"
        ]
        if not rollback_candidates:
            self.deactivate_knowledge_overlay_version(active_version.overlay_id)
            return None

        return self.activate_knowledge_overlay_version(rollback_candidates[-1].overlay_id)

    def archive_knowledge_overlay_version(self, overlay_id: int) -> KnowledgeOverlayVersion:
        target = self.get_knowledge_overlay_version(overlay_id)
        payload = target.model_dump(mode="json")
        payload["status"] = "archived"
        payload["activated_at"] = None
        payload.pop("overlay_id", None)
        with self.connection() as connection:
            connection.execute(
                "UPDATE knowledge_overlay_versions SET payload = ? WHERE id = ?",
                (json.dumps(payload), overlay_id),
            )
        return target.model_copy(update={"status": "archived", "activated_at": None})

    def clear_knowledge_overlays(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM knowledge_overlay_entries")
            connection.execute("DELETE FROM knowledge_overlay_versions")
            connection.execute("DELETE FROM knowledge_audit_logs")


persistence_service = SQLitePersistenceService(settings.sqlite_path)
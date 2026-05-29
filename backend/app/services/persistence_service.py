"""SQLite persistence layer for governed Semantra runtime and artifact state."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from contextlib import contextmanager

from app.core.config import settings
from app.models.knowledge import (
    CanonicalConceptUsageRecord,
    KnowledgeAuditEntry,
    KnowledgeOverlayEntry,
    KnowledgeOverlayVersion,
    KnowledgeStewardshipItemCreateRequest,
    KnowledgeStewardshipItemDetail,
    KnowledgeStewardshipItemRecord,
    SourceFieldHintRecord,
    SourceFieldHintUpsertRequest,
)
from app.models.mapping import (
    AutoMappingResponse,
    BenchmarkDatasetRecord,
    CatalogConceptDetail,
    CatalogConceptUsageRecord,
    CatalogIntegrationDetail,
    CatalogIntegrationRecord,
    CatalogSimilarIntegrationRecord,
    DecisionLogEntry,
    DraftSessionCreateRequest,
    DraftSessionDetail,
    DraftSessionRecord,
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
    """SQLite-backed persistence service for Semantra governance, catalog, and knowledge state."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def connection(self):
        """Yield a commit-on-success SQLite connection scoped to one persistence operation."""

        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_db(self) -> None:
        """Create or update the local SQLite schema used by Semantra runtime features."""

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
                CREATE TABLE IF NOT EXISTS draft_sessions (
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
                    workspace_id TEXT,
                    owner TEXT,
                    assignee TEXT,
                    created_at TEXT,
                    FOREIGN KEY(mapping_set_id) REFERENCES mapping_sets(id)
                )
                """
            )
            self._ensure_columns(
                connection,
                "mapping_catalog_entries",
                {
                    "workspace_id": "TEXT",
                },
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
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mapping_jobs (
                    job_id TEXT PRIMARY KEY,
                    created_by TEXT,
                    workspace_id TEXT,
                    worker_id TEXT,
                    status TEXT NOT NULL,
                    claimed_at TEXT,
                    heartbeat_at TEXT,
                    lease_expires_at TEXT,
                    recovery_signal TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at_monotonic REAL NOT NULL,
                    updated_at_monotonic REAL NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    canceled_at TEXT,
                    response_payload TEXT,
                    error TEXT
                )
                """
            )
            self._ensure_columns(
                connection,
                "mapping_jobs",
                {
                    "created_by": "TEXT",
                    "workspace_id": "TEXT",
                },
            )
            self._apply_named_migrations(connection)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mapping_jobs_status_updated ON mapping_jobs (status, updated_at_monotonic)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mapping_job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mapping_job_events_job_id ON mapping_job_events (job_id, id)"
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_stewardship_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    concept_id TEXT,
                    source TEXT,
                    target TEXT,
                    source_system TEXT,
                    business_domain TEXT,
                    owner TEXT,
                    assignee TEXT,
                    review_note TEXT,
                    created_by TEXT,
                    changed_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE(item_type, item_key)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_stewardship_type_status ON knowledge_stewardship_items (item_type, status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_stewardship_owner ON knowledge_stewardship_items (owner)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_stewardship_assignee ON knowledge_stewardship_items (assignee)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_field_hints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_system_key TEXT NOT NULL,
                    business_domain_key TEXT NOT NULL DEFAULT '',
                    integration_name_key TEXT NOT NULL DEFAULT '',
                    source_field_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE(source_system_key, business_domain_key, integration_name_key, source_field_key)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_source_field_hints_scope ON source_field_hints (source_system_key, business_domain_key, integration_name_key)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_concepts (
                    concept_id   TEXT PRIMARY KEY,
                    domain       TEXT NOT NULL DEFAULT '',
                    canonical_name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    context_terms_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_field_contexts (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_id         TEXT NOT NULL,
                    system             TEXT NOT NULL DEFAULT '',
                    object_name        TEXT NOT NULL DEFAULT '',
                    field_name         TEXT NOT NULL DEFAULT '',
                    category           TEXT NOT NULL DEFAULT '',
                    object_description TEXT NOT NULL DEFAULT '',
                    field_description  TEXT NOT NULL DEFAULT '',
                    note               TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(concept_id) REFERENCES knowledge_concepts(concept_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_kfc_concept ON knowledge_field_contexts(concept_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_concepts (
                    concept_id   TEXT PRIMARY KEY,
                    entity       TEXT NOT NULL DEFAULT '',
                    attribute    TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL,
                    description  TEXT NOT NULL DEFAULT '',
                    data_type    TEXT NOT NULL DEFAULT '',
                    aliases_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_field_contexts (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_id         TEXT NOT NULL,
                    system             TEXT NOT NULL DEFAULT '',
                    object_name        TEXT NOT NULL DEFAULT '',
                    field_name         TEXT NOT NULL DEFAULT '',
                    category           TEXT NOT NULL DEFAULT '',
                    object_description TEXT NOT NULL DEFAULT '',
                    field_description  TEXT NOT NULL DEFAULT '',
                    note               TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(concept_id) REFERENCES canonical_concepts(concept_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cfc_concept ON canonical_field_contexts(concept_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_seed_meta (
                    id              INTEGER PRIMARY KEY CHECK(id = 1),
                    seeded_at       TEXT NOT NULL,
                    source_hash     TEXT NOT NULL,
                    concept_count   INTEGER NOT NULL DEFAULT 0,
                    canonical_count INTEGER NOT NULL DEFAULT 0
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
            connection.execute("DELETE FROM mapping_job_events")
            connection.execute("DELETE FROM mapping_jobs")
            connection.execute("DELETE FROM knowledge_overlay_entries")
            connection.execute("DELETE FROM knowledge_overlay_versions")
            connection.execute("DELETE FROM knowledge_audit_logs")
            connection.execute("DELETE FROM knowledge_stewardship_items")
            connection.execute("DELETE FROM source_field_hints")

    def clear_decision_logs(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM decision_logs")

    def clear_user_corrections(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM user_corrections")

    def save_mapping_job(
        self,
        *,
        job_id: str,
        created_by: str | None = None,
        workspace_id: str | None = None,
        worker_id: str | None = None,
        status: str,
        claimed_at: str | None = None,
        heartbeat_at: str | None = None,
        lease_expires_at: str | None = None,
        recovery_signal: str | None = None,
        created_at: str,
        updated_at: str,
        created_at_monotonic: float,
        updated_at_monotonic: float,
        retry_count: int = 0,
        cancel_requested: bool = False,
        canceled_at: str | None = None,
        response: AutoMappingResponse | None = None,
        error: str | None = None,
    ) -> None:
        response_payload = response.model_dump_json() if response is not None else None
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO mapping_jobs (
                    job_id,
                    created_by,
                    workspace_id,
                    worker_id,
                    status,
                    claimed_at,
                    heartbeat_at,
                    lease_expires_at,
                    recovery_signal,
                    created_at,
                    updated_at,
                    created_at_monotonic,
                    updated_at_monotonic,
                    retry_count,
                    cancel_requested,
                    canceled_at,
                    response_payload,
                    error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    created_by = excluded.created_by,
                    workspace_id = excluded.workspace_id,
                    worker_id = excluded.worker_id,
                    status = excluded.status,
                    claimed_at = excluded.claimed_at,
                    heartbeat_at = excluded.heartbeat_at,
                    lease_expires_at = excluded.lease_expires_at,
                    recovery_signal = excluded.recovery_signal,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    created_at_monotonic = excluded.created_at_monotonic,
                    updated_at_monotonic = excluded.updated_at_monotonic,
                    retry_count = excluded.retry_count,
                    cancel_requested = excluded.cancel_requested,
                    canceled_at = excluded.canceled_at,
                    response_payload = excluded.response_payload,
                    error = excluded.error
                """,
                (
                    job_id,
                    created_by,
                    workspace_id,
                    worker_id,
                    status,
                    claimed_at,
                    heartbeat_at,
                    lease_expires_at,
                    recovery_signal,
                    created_at,
                    updated_at,
                    created_at_monotonic,
                    updated_at_monotonic,
                    retry_count,
                    1 if cancel_requested else 0,
                    canceled_at,
                    response_payload,
                    error,
                ),
            )

    def get_mapping_job(self, job_id: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    created_by,
                    workspace_id,
                    worker_id,
                    status,
                    claimed_at,
                    heartbeat_at,
                    lease_expires_at,
                    recovery_signal,
                    created_at,
                    updated_at,
                    created_at_monotonic,
                    updated_at_monotonic,
                    retry_count,
                    cancel_requested,
                    canceled_at,
                    response_payload,
                    error
                FROM mapping_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._mapping_job_from_row(row)

    def list_mapping_jobs(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    job_id,
                    created_by,
                    workspace_id,
                    worker_id,
                    status,
                    claimed_at,
                    heartbeat_at,
                    lease_expires_at,
                    recovery_signal,
                    created_at,
                    updated_at,
                    created_at_monotonic,
                    updated_at_monotonic,
                    retry_count,
                    cancel_requested,
                    canceled_at,
                    response_payload,
                    error
                FROM mapping_jobs
                ORDER BY created_at_monotonic ASC, job_id ASC
                """
            ).fetchall()
        return [self._mapping_job_from_row(row) for row in rows]

    def append_mapping_job_event(self, job_id: str, *, created_at: str, message: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO mapping_job_events (job_id, created_at, message) VALUES (?, ?, ?)",
                (job_id, created_at, message),
            )

    def list_mapping_job_events(self, job_id: str, *, limit: int | None = None) -> list[str]:
        query = "SELECT created_at, message FROM mapping_job_events WHERE job_id = ? ORDER BY id ASC"
        params: tuple[object, ...]
        params = (job_id,)
        if limit is not None:
            query = """
                SELECT created_at, message
                FROM (
                    SELECT id, created_at, message
                    FROM mapping_job_events
                    WHERE job_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) recent_events
                ORDER BY id ASC
            """
            params = (job_id, limit)
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [f"{self._time_only(row[0])} | {row[1]}" for row in rows]

    def trim_mapping_job_events(self, job_id: str, *, keep_last: int) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                DELETE FROM mapping_job_events
                WHERE job_id = ?
                  AND id NOT IN (
                      SELECT id
                      FROM mapping_job_events
                      WHERE job_id = ?
                      ORDER BY id DESC
                      LIMIT ?
                  )
                """,
                (job_id, job_id, keep_last),
            )

    def delete_mapping_jobs(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        placeholders = ",".join("?" for _ in job_ids)
        with self.connection() as connection:
            connection.execute(f"DELETE FROM mapping_job_events WHERE job_id IN ({placeholders})", job_ids)
            connection.execute(f"DELETE FROM mapping_jobs WHERE job_id IN ({placeholders})", job_ids)

    def clear_mapping_jobs(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM mapping_job_events")
            connection.execute("DELETE FROM mapping_jobs")

    def fail_active_mapping_jobs(self, *, updated_at: str, updated_at_monotonic: float, message: str, error: str) -> int:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT job_id FROM mapping_jobs WHERE status IN ('queued', 'running', 'cancel_requested') ORDER BY job_id ASC"
            ).fetchall()
            job_ids = [str(row[0]) for row in rows]
            if not job_ids:
                return 0
            for job_id in job_ids:
                connection.execute(
                    "INSERT INTO mapping_job_events (job_id, created_at, message) VALUES (?, ?, ?)",
                    (job_id, updated_at, message),
                )
                connection.execute(
                    """
                    UPDATE mapping_jobs
                    SET status = 'failed',
                        lease_expires_at = NULL,
                        recovery_signal = 'worker_runtime_restarted',
                        updated_at = ?,
                        updated_at_monotonic = ?,
                        error = ?,
                        cancel_requested = 0
                    WHERE job_id = ?
                    """,
                    (updated_at, updated_at_monotonic, error, job_id),
                )
        return len(job_ids)

    def _mapping_job_from_row(self, row: sqlite3.Row | tuple[object, ...]) -> dict:
        response_payload = row[16]
        return {
            "job_id": str(row[0]),
            "created_by": row[1],
            "workspace_id": row[2],
            "worker_id": row[3],
            "status": str(row[4]),
            "claimed_at": row[5],
            "heartbeat_at": row[6],
            "lease_expires_at": row[7],
            "recovery_signal": row[8],
            "created_at": str(row[9]),
            "updated_at": str(row[10]),
            "created_at_monotonic": float(row[11]),
            "updated_at_monotonic": float(row[12]),
            "retry_count": int(row[13]),
            "cancel_requested": bool(row[14]),
            "canceled_at": row[15],
            "response": AutoMappingResponse.model_validate(json.loads(response_payload)) if response_payload else None,
            "error": row[17],
        }

    def _apply_named_migrations(self, connection: sqlite3.Connection) -> None:
        applied = {
            str(row[0])
            for row in connection.execute("SELECT migration_name FROM schema_migrations").fetchall()
        }
        migrations: list[tuple[str, callable]] = [
            ("20260528_mapping_jobs_runtime_metadata", self._migrate_mapping_jobs_runtime_metadata),
        ]
        for migration_name, migration in migrations:
            if migration_name in applied:
                continue
            migration(connection)
            connection.execute(
                "INSERT INTO schema_migrations (migration_name, applied_at) VALUES (?, ?)",
                (migration_name, datetime.now(UTC).isoformat()),
            )

    def _migrate_mapping_jobs_runtime_metadata(self, connection: sqlite3.Connection) -> None:
        self._ensure_columns(
            connection,
            "mapping_jobs",
            {
                "worker_id": "TEXT",
                "claimed_at": "TEXT",
                "heartbeat_at": "TEXT",
                "lease_expires_at": "TEXT",
                "recovery_signal": "TEXT",
            },
        )

    def _ensure_columns(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        columns: dict[str, str],
    ) -> None:
        existing = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_type in columns.items():
            if column_name in existing:
                continue
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def _time_only(self, timestamp: str) -> str:
        try:
            return datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
        except ValueError:
            return str(timestamp)

    def save_source_field_hint(
        self,
        request: SourceFieldHintUpsertRequest | dict,
    ) -> SourceFieldHintRecord:
        payload = request if isinstance(request, SourceFieldHintUpsertRequest) else SourceFieldHintUpsertRequest.model_validate(request)
        normalized_source_system = self._normalize_key(payload.source_system)
        normalized_business_domain = self._normalize_key(payload.business_domain)
        normalized_integration_name = self._normalize_key(payload.integration_name)
        normalized_source_field = self._normalize_key(payload.source_field)
        if not normalized_source_system:
            raise ValueError("Source field hints require a source system.")
        if not normalized_source_field:
            raise ValueError("Source field hints require a source field name.")

        meaning_hint = str(payload.meaning_hint or "").strip()
        negative_hint = str(payload.negative_hint or "").strip()
        sample_values = self._normalize_text_list(payload.sample_values)
        if not meaning_hint and not negative_hint and not sample_values:
            raise ValueError("Provide meaning, negative guidance, or sample values before saving a source field hint.")

        now = datetime.now(UTC).isoformat()
        with self.connection() as connection:
            existing = connection.execute(
                (
                    "SELECT id, payload FROM source_field_hints "
                    "WHERE source_system_key = ? AND business_domain_key = ? AND integration_name_key = ? AND source_field_key = ?"
                ),
                (
                    normalized_source_system,
                    normalized_business_domain,
                    normalized_integration_name,
                    normalized_source_field,
                ),
            ).fetchone()

            if existing:
                existing_record = SourceFieldHintRecord.model_validate(
                    {
                        **json.loads(existing[1]),
                        "hint_id": int(existing[0]),
                    }
                )
                updated_record = SourceFieldHintRecord(
                    hint_id=int(existing[0]),
                    source_system=str(payload.source_system).strip(),
                    business_domain=self._clean_optional_text(payload.business_domain),
                    integration_name=self._clean_optional_text(payload.integration_name),
                    source_field=str(payload.source_field).strip(),
                    meaning_hint=meaning_hint,
                    negative_hint=negative_hint,
                    sample_values=sample_values,
                    active=bool(payload.active),
                    created_by=existing_record.created_by or payload.created_by,
                    changed_by=payload.changed_by or payload.created_by,
                    created_at=existing_record.created_at or now,
                    updated_at=now,
                )
                connection.execute(
                    (
                        "UPDATE source_field_hints SET payload = ? "
                        "WHERE source_system_key = ? AND business_domain_key = ? AND integration_name_key = ? AND source_field_key = ?"
                    ),
                    (
                        updated_record.model_dump_json(),
                        normalized_source_system,
                        normalized_business_domain,
                        normalized_integration_name,
                        normalized_source_field,
                    ),
                )
                return updated_record

            saved_record = SourceFieldHintRecord(
                source_system=str(payload.source_system).strip(),
                business_domain=self._clean_optional_text(payload.business_domain),
                integration_name=self._clean_optional_text(payload.integration_name),
                source_field=str(payload.source_field).strip(),
                meaning_hint=meaning_hint,
                negative_hint=negative_hint,
                sample_values=sample_values,
                active=bool(payload.active),
                created_by=payload.created_by,
                changed_by=payload.changed_by or payload.created_by,
                created_at=now,
                updated_at=now,
            )
            cursor = connection.execute(
                (
                    "INSERT INTO source_field_hints (source_system_key, business_domain_key, integration_name_key, source_field_key, payload) "
                    "VALUES (?, ?, ?, ?, ?)"
                ),
                (
                    normalized_source_system,
                    normalized_business_domain,
                    normalized_integration_name,
                    normalized_source_field,
                    saved_record.model_dump_json(),
                ),
            )
        return saved_record.model_copy(update={"hint_id": int(cursor.lastrowid)})

    def list_source_field_hints(
        self,
        *,
        source_system: str | None = None,
        business_domain: str | None = None,
        integration_name: str | None = None,
        source_field: str | None = None,
        active_only: bool = True,
    ) -> list[SourceFieldHintRecord]:
        query = "SELECT id, payload FROM source_field_hints WHERE 1 = 1"
        params: list[str] = []
        if source_system is not None:
            query += " AND source_system_key = ?"
            params.append(self._normalize_key(source_system))
        if business_domain is not None:
            query += " AND business_domain_key = ?"
            params.append(self._normalize_key(business_domain))
        if integration_name is not None:
            query += " AND integration_name_key = ?"
            params.append(self._normalize_key(integration_name))
        if source_field is not None:
            query += " AND source_field_key = ?"
            params.append(self._normalize_key(source_field))
        query += " ORDER BY id ASC"

        with self.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        records = [
            SourceFieldHintRecord.model_validate(
                {
                    **json.loads(row[1]),
                    "hint_id": int(row[0]),
                }
            )
            for row in rows
        ]
        if active_only:
            return [record for record in records if record.active]
        return records

    def clear_source_field_hints(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM source_field_hints")

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
        workspace_id: str | None = None,
        note: str | None = None,
        owner: str | None = None,
        assignee: str | None = None,
        review_note: str | None = None,
    ) -> MappingSetRecord:
        """Persist one governed mapping-set version and refresh its catalog projection."""

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
                "workspace_id": workspace_id,
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
                    workspace_id,
                    owner,
                    assignee,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    workspace_id,
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
            workspace_id=workspace_id,
            note=note,
            owner=owner,
            assignee=assignee,
            review_note=review_note,
            created_at=created_at,
        )

    def list_mapping_sets(self) -> list[MappingSetRecord]:
        """List saved mapping-set versions with their governance metadata."""

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
                    workspace_id=payload.get("workspace_id"),
                    note=payload.get("note"),
                    owner=payload.get("owner"),
                    assignee=payload.get("assignee"),
                    review_note=payload.get("review_note"),
                    created_at=payload.get("created_at"),
                )
            )
        return records

    def get_mapping_set(self, mapping_set_id: int) -> MappingSetDetail:
        """Load one mapping-set version together with its stored decision payload."""

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
            workspace_id=payload.get("workspace_id"),
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
        """List catalog integration records projected from persisted mapping-set history."""

        query = (
            "SELECT mapping_set_id, name, integration_name, version, status, artifact_type, decision_count, "
            "source_dataset_id, target_dataset_id, source_system, target_system, business_domain, interface_type, "
            "description, canonical_concepts_json, unmatched_sources_json, created_by, workspace_id, owner, assignee, created_at "
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
            "description, canonical_concepts_json, unmatched_sources_json, created_by, workspace_id, owner, assignee, created_at "
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
        """Load one catalog integration with version history and similar-integration hints."""

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
            workspace_id=latest_version.workspace_id,
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
        integrations = self.list_catalog_concept_usage_records(
            concept_id,
            source_system=source_system,
            target_system=target_system,
            status=status,
            artifact_type=artifact_type,
        )
        if not integrations:
            raise KeyError(f"Unknown catalog concept: {concept_id}")
        return CatalogConceptDetail(
            concept_id=concept_id,
            usage_count=len(integrations),
            integrations=[
                CatalogConceptUsageRecord.model_validate(record.model_dump(mode="json"))
                for record in integrations
            ],
        )

    def list_catalog_concept_usage_counts(self) -> dict[str, int]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT concept_id, COUNT(*) FROM mapping_catalog_concepts GROUP BY concept_id"
            ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def list_catalog_concept_usage_facets(self) -> dict[str, dict[str, list[str]]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT concept_id, source_system, business_domain FROM mapping_catalog_concepts"
            ).fetchall()

        facets: dict[str, dict[str, set[str]]] = {}
        for row in rows:
            concept_id = str(row[0])
            concept_facets = facets.setdefault(
                concept_id,
                {"source_systems": set(), "business_domains": set()},
            )
            source_system = str(row[1] or "").strip()
            business_domain = str(row[2] or "").strip()
            if source_system:
                concept_facets["source_systems"].add(source_system)
            if business_domain:
                concept_facets["business_domains"].add(business_domain)

        return {
            concept_id: {
                "source_systems": sorted(values["source_systems"]),
                "business_domains": sorted(values["business_domains"]),
            }
            for concept_id, values in facets.items()
        }

    def list_catalog_concept_usage_records(
        self,
        concept_id: str,
        *,
        source_system: str | None = None,
        target_system: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> list[CanonicalConceptUsageRecord]:
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
        return [
            CanonicalConceptUsageRecord(
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

    def save_draft_session(self, request: DraftSessionCreateRequest) -> DraftSessionRecord:
        """Persist one durable draft workspace snapshot for later resume."""

        created_at = datetime.now(UTC).isoformat()
        decision_count = len(request.mapping_editor_state)
        normalized_decision_audit = self._normalize_draft_session_decision_audit(
            request.mapping_decision_audit,
            created_by=request.created_by,
            workspace_id=request.workspace_id,
        )
        payload = DraftSessionDetail(
            draft_session_id=0,
            name=request.name,
            created_by=request.created_by,
            workspace_id=request.workspace_id,
            api_base_url=request.api_base_url,
            mapping_mode=request.mapping_mode,
            active_workspace_section=request.active_workspace_section,
            source_dataset_name=request.source_handle.dataset_name,
            target_dataset_name=request.target_handle.dataset_name if request.target_handle else "",
            canonical_target_system=request.canonical_target_system,
            workspace_target_context=request.workspace_target_context,
            review_state=request.review_state,
            decision_count=decision_count,
            version=1,
            last_writer=request.created_by,
            created_at=created_at,
            updated_at=created_at,
            source_handle=request.source_handle,
            target_handle=request.target_handle,
            mapping_runtime=request.mapping_runtime,
            mapping_editor_state=request.mapping_editor_state,
            mapping_decision_audit=normalized_decision_audit,
        )
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO draft_sessions (name, payload) VALUES (?, ?)",
                (request.name, payload.model_dump_json(exclude={"draft_session_id"})),
            )
            draft_session_id = int(cursor.lastrowid)
        return payload.model_copy(update={"draft_session_id": draft_session_id})

    def update_draft_session(self, draft_session_id: int, request) -> DraftSessionDetail:
        """Update one durable draft workspace snapshot with optimistic concurrency."""

        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM draft_sessions WHERE id = ?",
                (draft_session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown draft session id: {draft_session_id}")

            payload = json.loads(row[0])
            current_detail = DraftSessionDetail.model_validate({**payload, "draft_session_id": draft_session_id})
            if int(current_detail.version or 1) != int(request.expected_version):
                raise DraftSessionStaleWriteError(current_detail, int(request.expected_version))

            normalized_decision_audit = self._normalize_draft_session_decision_audit(
                request.mapping_decision_audit,
                created_by=current_detail.created_by or request.created_by,
                workspace_id=current_detail.workspace_id or request.workspace_id,
            )
            decision_count = len(request.mapping_editor_state)
            durable_state_changed = any(
                [
                    current_detail.name != request.name,
                    current_detail.api_base_url != request.api_base_url,
                    current_detail.mapping_mode != request.mapping_mode,
                    current_detail.active_workspace_section != request.active_workspace_section,
                    current_detail.canonical_target_system != request.canonical_target_system,
                    current_detail.workspace_target_context != request.workspace_target_context,
                    current_detail.review_state != request.review_state,
                    current_detail.source_handle.model_dump(mode="json") != request.source_handle.model_dump(mode="json"),
                    (current_detail.target_handle.model_dump(mode="json") if current_detail.target_handle else None)
                    != (request.target_handle.model_dump(mode="json") if request.target_handle else None),
                    current_detail.mapping_runtime.model_dump(mode="json") != request.mapping_runtime.model_dump(mode="json"),
                    current_detail.mapping_editor_state != request.mapping_editor_state,
                    current_detail.mapping_decision_audit != normalized_decision_audit,
                ]
            )
            if not durable_state_changed:
                return current_detail

            updated_at = datetime.now(UTC).isoformat()
            updated_detail = DraftSessionDetail(
                draft_session_id=draft_session_id,
                name=request.name,
                created_by=current_detail.created_by or request.created_by,
                workspace_id=current_detail.workspace_id or request.workspace_id,
                api_base_url=request.api_base_url,
                mapping_mode=request.mapping_mode,
                active_workspace_section=request.active_workspace_section,
                source_dataset_name=request.source_handle.dataset_name,
                target_dataset_name=request.target_handle.dataset_name if request.target_handle else "",
                canonical_target_system=request.canonical_target_system,
                workspace_target_context=request.workspace_target_context,
                review_state=request.review_state,
                decision_count=decision_count,
                version=int(current_detail.version or 1) + 1,
                last_writer=(request.last_writer or request.created_by or current_detail.last_writer),
                created_at=current_detail.created_at,
                updated_at=updated_at,
                source_handle=request.source_handle,
                target_handle=request.target_handle,
                mapping_runtime=request.mapping_runtime,
                mapping_editor_state=request.mapping_editor_state,
                mapping_decision_audit=normalized_decision_audit,
            )
            connection.execute(
                "UPDATE draft_sessions SET name = ?, payload = ? WHERE id = ?",
                (
                    request.name,
                    updated_detail.model_dump_json(exclude={"draft_session_id"}),
                    draft_session_id,
                ),
            )
        return updated_detail

    def list_draft_sessions(self) -> list[DraftSessionRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, name, payload FROM draft_sessions ORDER BY id DESC"
            ).fetchall()
        records: list[DraftSessionRecord] = []
        for row in rows:
            payload = json.loads(row[2])
            records.append(
                DraftSessionRecord(
                    draft_session_id=int(row[0]),
                    name=row[1],
                    created_by=payload.get("created_by"),
                    workspace_id=payload.get("workspace_id"),
                    api_base_url=payload.get("api_base_url", ""),
                    mapping_mode=payload.get("mapping_mode", "standard"),
                    active_workspace_section=payload.get("active_workspace_section", "Review"),
                    source_dataset_name=payload.get("source_dataset_name", ""),
                    target_dataset_name=payload.get("target_dataset_name", ""),
                    canonical_target_system=payload.get("canonical_target_system"),
                    workspace_target_context=payload.get("workspace_target_context") or {},
                    review_state=payload.get("review_state") or {},
                    decision_count=payload.get("decision_count", len(payload.get("mapping_editor_state", {}))),
                    version=payload.get("version", 1),
                    last_writer=payload.get("last_writer") or payload.get("created_by"),
                    created_at=payload.get("created_at"),
                    updated_at=payload.get("updated_at"),
                )
            )
        return records

    def get_draft_session(self, draft_session_id: int) -> DraftSessionDetail:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM draft_sessions WHERE id = ?",
                (draft_session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown draft session id: {draft_session_id}")
        payload = json.loads(row[0])
        return DraftSessionDetail.model_validate({**payload, "draft_session_id": draft_session_id})

    def _normalize_draft_session_decision_audit(
        self,
        mapping_decision_audit: dict,
        *,
        created_by: str | None,
        workspace_id: str | None,
    ) -> dict:
        return {
            source_name: audit_entry.model_copy(
                update={
                    "created_by": audit_entry.created_by or created_by,
                    "workspace_id": audit_entry.workspace_id or workspace_id,
                }
            )
            for source_name, audit_entry in mapping_decision_audit.items()
        }

    def clear_draft_sessions(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM draft_sessions")

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
            workspace_id=row[17],
            owner=row[18],
            assignee=row[19],
            created_at=row[20],
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

    def _normalize_key(self, value: str | None) -> str:
        return str(value or "").strip().lower()

    def _clean_optional_text(self, value: object | None) -> str | None:
        text = str(value or "").strip()
        return text or None

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
                        workspace_id,
                        owner,
                        assignee,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        detail.workspace_id,
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

    def save_benchmark_dataset(
        self,
        name: str,
        cases: list[dict],
        *,
        created_by: str | None = None,
        workspace_id: str | None = None,
    ) -> BenchmarkDatasetRecord:
        """Persist a reusable benchmark dataset for later evaluation runs."""

        version = 1 + max(
            (record.version for record in self.list_benchmark_datasets() if record.name == name),
            default=0,
        )
        created_at = datetime.now(UTC).isoformat()
        payload = json.dumps(
            {
                "cases": cases,
                "version": version,
                "created_by": created_by,
                "workspace_id": workspace_id,
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
            created_by=created_by,
            workspace_id=workspace_id,
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
                    created_by=payload.get("created_by"),
                    workspace_id=payload.get("workspace_id"),
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
        *,
        created_by: str | None = None,
        workspace_id: str | None = None,
    ) -> EvaluationRunRecord:
        created_at = datetime.now(UTC).isoformat()
        payload = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "provider_name": provider_name,
            "created_by": created_by,
            "workspace_id": workspace_id,
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

    def _knowledge_stewardship_detail_from_row(self, row: sqlite3.Row | tuple) -> KnowledgeStewardshipItemDetail:
        payload = json.loads(row[17])
        return KnowledgeStewardshipItemDetail(
            item_id=int(row[0]),
            item_type=row[1],
            item_key=row[2],
            title=row[3],
            status=row[4],
            concept_id=row[5],
            source=row[6],
            target=row[7],
            source_system=row[8],
            business_domain=row[9],
            owner=row[10],
            assignee=row[11],
            review_note=row[12],
            created_by=row[13],
            changed_by=row[14],
            created_at=row[15],
            updated_at=row[16],
            candidate_payload=payload.get("candidate_payload") or {},
            suggestion_payload=payload.get("suggestion_payload") or {},
            overlay_entry_payload=payload.get("overlay_entry_payload") or {},
        )

    def list_knowledge_stewardship_items(
        self,
        *,
        item_type: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        assignee: str | None = None,
    ) -> list[KnowledgeStewardshipItemRecord]:
        query = (
            "SELECT id, item_type, item_key, title, status, concept_id, source, target, source_system, "
            "business_domain, owner, assignee, review_note, created_by, changed_by, created_at, updated_at, payload "
            "FROM knowledge_stewardship_items WHERE 1 = 1"
        )
        params: list[object] = []
        if item_type:
            query += " AND item_type = ?"
            params.append(item_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        if assignee:
            query += " AND assignee = ?"
            params.append(assignee)
        query += " ORDER BY updated_at DESC, id DESC"

        with self.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [KnowledgeStewardshipItemRecord.model_validate(self._knowledge_stewardship_detail_from_row(row).model_dump(mode="json")) for row in rows]

    def get_knowledge_stewardship_item(self, item_id: int) -> KnowledgeStewardshipItemDetail:
        with self.connection() as connection:
            row = connection.execute(
                (
                    "SELECT id, item_type, item_key, title, status, concept_id, source, target, source_system, "
                    "business_domain, owner, assignee, review_note, created_by, changed_by, created_at, updated_at, payload "
                    "FROM knowledge_stewardship_items WHERE id = ?"
                ),
                (item_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown knowledge stewardship item id: {item_id}")
        return self._knowledge_stewardship_detail_from_row(row)

    def get_knowledge_stewardship_item_by_key(self, item_type: str, item_key: str) -> KnowledgeStewardshipItemDetail | None:
        with self.connection() as connection:
            row = connection.execute(
                (
                    "SELECT id, item_type, item_key, title, status, concept_id, source, target, source_system, "
                    "business_domain, owner, assignee, review_note, created_by, changed_by, created_at, updated_at, payload "
                    "FROM knowledge_stewardship_items WHERE item_type = ? AND item_key = ?"
                ),
                (item_type, item_key),
            ).fetchone()
        if row is None:
            return None
        return self._knowledge_stewardship_detail_from_row(row)

    def upsert_knowledge_stewardship_item(
        self,
        request: KnowledgeStewardshipItemCreateRequest,
    ) -> KnowledgeStewardshipItemDetail:
        existing = self.get_knowledge_stewardship_item_by_key(request.item_type, request.item_key)
        now = datetime.now(UTC).isoformat()
        created_at = existing.created_at if existing and existing.created_at else now
        created_by = existing.created_by if existing and existing.created_by else request.created_by
        payload_json = json.dumps(
            {
                "candidate_payload": request.candidate_payload,
                "suggestion_payload": request.suggestion_payload,
                "overlay_entry_payload": request.overlay_entry_payload,
            }
        )
        title = (request.title or "").strip() or request.item_key
        with self.connection() as connection:
            if existing is None:
                cursor = connection.execute(
                    (
                        "INSERT INTO knowledge_stewardship_items ("
                        "item_type, item_key, title, status, concept_id, source, target, source_system, business_domain, "
                        "owner, assignee, review_note, created_by, changed_by, created_at, updated_at, payload"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    ),
                    (
                        request.item_type,
                        request.item_key,
                        title,
                        request.status,
                        request.concept_id,
                        request.source,
                        request.target,
                        request.source_system,
                        request.business_domain,
                        request.owner,
                        request.assignee,
                        request.review_note,
                        created_by,
                        request.changed_by,
                        created_at,
                        now,
                        payload_json,
                    ),
                )
                item_id = int(cursor.lastrowid)
            else:
                item_id = existing.item_id
                connection.execute(
                    (
                        "UPDATE knowledge_stewardship_items SET "
                        "title = ?, status = ?, concept_id = ?, source = ?, target = ?, source_system = ?, business_domain = ?, "
                        "owner = ?, assignee = ?, review_note = ?, created_by = ?, changed_by = ?, created_at = ?, updated_at = ?, payload = ? "
                        "WHERE id = ?"
                    ),
                    (
                        title,
                        request.status,
                        request.concept_id,
                        request.source,
                        request.target,
                        request.source_system,
                        request.business_domain,
                        request.owner,
                        request.assignee,
                        request.review_note,
                        created_by,
                        request.changed_by,
                        created_at,
                        now,
                        payload_json,
                        item_id,
                    ),
                )
        return self.get_knowledge_stewardship_item(item_id)

    def update_knowledge_stewardship_item_status(
        self,
        item_id: int,
        status: str,
        *,
        changed_by: str | None = None,
        owner: str | None = None,
        assignee: str | None = None,
        review_note: str | None = None,
    ) -> KnowledgeStewardshipItemDetail:
        existing = self.get_knowledge_stewardship_item(item_id)
        payload_json = json.dumps(
            {
                "candidate_payload": existing.candidate_payload,
                "suggestion_payload": existing.suggestion_payload,
                "overlay_entry_payload": existing.overlay_entry_payload,
            }
        )
        with self.connection() as connection:
            connection.execute(
                (
                    "UPDATE knowledge_stewardship_items SET status = ?, owner = ?, assignee = ?, review_note = ?, changed_by = ?, updated_at = ?, payload = ? "
                    "WHERE id = ?"
                ),
                (
                    status,
                    existing.owner if owner is None else owner,
                    existing.assignee if assignee is None else assignee,
                    existing.review_note if review_note is None else review_note,
                    changed_by,
                    datetime.now(UTC).isoformat(),
                    payload_json,
                    item_id,
                ),
            )
        return self.get_knowledge_stewardship_item(item_id)

    def clear_knowledge_stewardship_items(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM knowledge_stewardship_items")

    def save_knowledge_overlay_version(
        self,
        name: str,
        *,
        status: str = "draft",
        scope: str = "global",
        created_by: str | None = None,
        source_filename: str | None = None,
    ) -> KnowledgeOverlayVersion:
        """Persist one knowledge overlay version record before its rows are stored."""

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
        if target.status not in {"validated", "active"}:
            raise ValueError(f"Only validated knowledge overlays can be activated. Current status: {target.status}.")
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
        if target.status not in {"validated", "active"}:
            raise ValueError(
                f"Only validated or active knowledge overlays can be archived. Current status: {target.status}."
            )
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

    # ------------------------------------------------------------------
    # Knowledge base persistence (canonical concepts + knowledge concepts)
    # ------------------------------------------------------------------

    def get_knowledge_seed_meta(self) -> dict | None:
        """Return the seed metadata row, or None if the DB has never been seeded."""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT seeded_at, source_hash, concept_count, canonical_count FROM knowledge_seed_meta WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "seeded_at":       row[0],
            "source_hash":     row[1],
            "concept_count":   row[2],
            "canonical_count": row[3],
        }

    def save_knowledge_seed_meta(
        self,
        source_hash: str,
        concept_count: int,
        canonical_count: int,
        seeded_at: str | None = None,
    ) -> None:
        from datetime import UTC, datetime
        ts = seeded_at or datetime.now(UTC).isoformat()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_seed_meta (id, seeded_at, source_hash, concept_count, canonical_count)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    seeded_at       = excluded.seeded_at,
                    source_hash     = excluded.source_hash,
                    concept_count   = excluded.concept_count,
                    canonical_count = excluded.canonical_count
                """,
                (ts, source_hash, concept_count, canonical_count),
            )

    def seed_knowledge_concepts(
        self,
        concepts: list,   # list[KnowledgeConcept] — typed in caller
        canonical_concepts: list,  # list[CanonicalBusinessConcept]
        canonical_field_contexts: list[tuple[str, object]],
    ) -> None:
        """Replace the entire knowledge base in the DB atomically."""
        with self.connection() as connection:
            connection.execute("DELETE FROM canonical_field_contexts")
            connection.execute("DELETE FROM knowledge_field_contexts")
            connection.execute("DELETE FROM knowledge_concepts")
            connection.execute("DELETE FROM canonical_concepts")

            for c in concepts:
                connection.execute(
                    """
                    INSERT INTO knowledge_concepts
                        (concept_id, domain, canonical_name, aliases_json, context_terms_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        c.concept_id,
                        c.domain,
                        c.canonical_name,
                        json.dumps(sorted(c.aliases)),
                        json.dumps(sorted(c.context_terms)),
                    ),
                )
                for ctx in c.contexts:
                    connection.execute(
                        """
                        INSERT INTO knowledge_field_contexts
                            (concept_id, system, object_name, field_name,
                             category, object_description, field_description, note)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c.concept_id,
                            ctx.system,
                            ctx.object_name,
                            ctx.field_name,
                            ctx.category,
                            ctx.object_description,
                            ctx.field_description,
                            ctx.note,
                        ),
                    )

            for cc in canonical_concepts:
                connection.execute(
                    """
                    INSERT INTO canonical_concepts
                        (concept_id, entity, attribute, display_name, description, data_type, aliases_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cc.concept_id,
                        cc.entity,
                        cc.attribute,
                        cc.display_name,
                        cc.description,
                        cc.data_type,
                        json.dumps(sorted(cc.aliases)),
                    ),
                )

            for concept_id, ctx in canonical_field_contexts:
                connection.execute(
                    """
                    INSERT INTO canonical_field_contexts
                        (concept_id, system, object_name, field_name,
                         category, object_description, field_description, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        concept_id,
                        ctx.system,
                        ctx.object_name,
                        ctx.field_name,
                        ctx.category,
                        ctx.object_description,
                        ctx.field_description,
                        ctx.note,
                    ),
                )

    def sync_canonical_runtime(
        self,
        canonical_concepts: list,
        canonical_field_contexts: list[tuple[str, object]],
        *,
        source_hash: str,
        concept_count: int,
        seeded_at: str | None = None,
    ) -> None:
        """Refresh only canonical runtime tables while preserving persisted knowledge concepts."""

        with self.connection() as connection:
            connection.execute("DELETE FROM canonical_field_contexts")
            connection.execute("DELETE FROM canonical_concepts")

            for cc in canonical_concepts:
                connection.execute(
                    """
                    INSERT INTO canonical_concepts
                        (concept_id, entity, attribute, display_name, description, data_type, aliases_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cc.concept_id,
                        cc.entity,
                        cc.attribute,
                        cc.display_name,
                        cc.description,
                        cc.data_type,
                        json.dumps(sorted(cc.aliases)),
                    ),
                )

            for concept_id, ctx in canonical_field_contexts:
                connection.execute(
                    """
                    INSERT INTO canonical_field_contexts
                        (concept_id, system, object_name, field_name,
                         category, object_description, field_description, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        concept_id,
                        ctx.system,
                        ctx.object_name,
                        ctx.field_name,
                        ctx.category,
                        ctx.object_description,
                        ctx.field_description,
                        ctx.note,
                    ),
                )

        self.save_knowledge_seed_meta(
            source_hash=source_hash,
            concept_count=concept_count,
            canonical_count=len(canonical_concepts),
            seeded_at=seeded_at,
        )

    def load_knowledge_concepts(self) -> tuple[list, list, list]:
        """Return persisted knowledge concepts, canonical concepts, and canonical field contexts."""
        with self.connection() as connection:
            kc_rows = connection.execute(
                "SELECT concept_id, domain, canonical_name, aliases_json, context_terms_json FROM knowledge_concepts"
            ).fetchall()
            ctx_rows = connection.execute(
                """
                SELECT concept_id, system, object_name, field_name,
                       category, object_description, field_description, note
                FROM knowledge_field_contexts
                """
            ).fetchall()
            cc_rows = connection.execute(
                "SELECT concept_id, entity, attribute, display_name, description, data_type, aliases_json FROM canonical_concepts"
            ).fetchall()
            canonical_ctx_rows = connection.execute(
                """
                SELECT concept_id, system, object_name, field_name,
                       category, object_description, field_description, note
                FROM canonical_field_contexts
                """
            ).fetchall()

        # Group contexts by concept_id
        contexts_by_concept: dict[str, list[dict]] = {}
        for row in ctx_rows:
            contexts_by_concept.setdefault(row[0], []).append({
                "system": row[1], "object_name": row[2], "field_name": row[3],
                "category": row[4], "object_description": row[5],
                "field_description": row[6], "note": row[7],
            })

        knowledge_dicts = [
            {
                "concept_id":    row[0],
                "domain":        row[1],
                "canonical_name": row[2],
                "aliases":       json.loads(row[3]),
                "context_terms": json.loads(row[4]),
                "contexts":      contexts_by_concept.get(row[0], []),
            }
            for row in kc_rows
        ]
        canonical_dicts = [
            {
                "concept_id":   row[0],
                "entity":       row[1],
                "attribute":    row[2],
                "display_name": row[3],
                "description":  row[4],
                "data_type":    row[5],
                "aliases":      json.loads(row[6]),
            }
            for row in cc_rows
        ]
        canonical_context_dicts = [
            {
                "concept_id": row[0],
                "system": row[1],
                "object_name": row[2],
                "field_name": row[3],
                "category": row[4],
                "object_description": row[5],
                "field_description": row[6],
                "note": row[7],
            }
            for row in canonical_ctx_rows
        ]
        return knowledge_dicts, canonical_dicts, canonical_context_dicts


persistence_service = SQLitePersistenceService(settings.sqlite_path)


class DraftSessionStaleWriteError(RuntimeError):
    """Raised when a draft session update uses an outdated expected version."""

    def __init__(self, current_detail: DraftSessionDetail, expected_version: int) -> None:
        self.current_detail = current_detail
        self.expected_version = expected_version
        super().__init__(
            f"Draft session {current_detail.draft_session_id} expected version {expected_version} does not match current version {current_detail.version}."
        )

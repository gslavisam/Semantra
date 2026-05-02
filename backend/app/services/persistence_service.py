from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from contextlib import contextmanager

from app.core.config import settings
from app.models.knowledge import KnowledgeAuditEntry, KnowledgeOverlayEntry, KnowledgeOverlayVersion
from app.models.mapping import (
    BenchmarkDatasetRecord,
    DecisionLogEntry,
    EvaluationMetrics,
    EvaluationRunRecord,
    MappingSetAuditEntry,
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
            rows = connection.execute("SELECT payload FROM user_corrections ORDER BY id ASC").fetchall()
        return [UserCorrectionEntry.model_validate(json.loads(row[0])) for row in rows]

    def clear_all(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM decision_logs")
            connection.execute("DELETE FROM user_corrections")
            connection.execute("DELETE FROM reusable_correction_rules")
            connection.execute("DELETE FROM mapping_set_audit_logs")
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
        created_by: str | None = None,
        note: str | None = None,
    ) -> MappingSetRecord:
        version = 1 + max(
            (record.version for record in self.list_mapping_sets() if record.name == name),
            default=0,
        )
        created_at = datetime.now(UTC).isoformat()
        payload = json.dumps(
            {
                "status": status,
                "version": version,
                "decision_count": len(mapping_decisions),
                "source_dataset_id": source_dataset_id,
                "target_dataset_id": target_dataset_id,
                "created_by": created_by,
                "note": note,
                "created_at": created_at,
                "mapping_decisions": [
                    decision.model_dump(mode="json") if hasattr(decision, "model_dump") else decision
                    for decision in mapping_decisions
                ],
            }
        )
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO mapping_sets (name, payload) VALUES (?, ?)",
                (name, payload),
            )
            mapping_set_id = int(cursor.lastrowid)
        return MappingSetRecord(
            mapping_set_id=mapping_set_id,
            name=name,
            status=status,
            version=version,
            decision_count=len(mapping_decisions),
            source_dataset_id=source_dataset_id,
            target_dataset_id=target_dataset_id,
            created_by=created_by,
            note=note,
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
                    created_by=payload.get("created_by"),
                    note=payload.get("note"),
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
            created_by=payload.get("created_by"),
            note=payload.get("note"),
            created_at=payload.get("created_at"),
            mapping_decisions=payload.get("mapping_decisions", []),
        )

    def update_mapping_set_status(self, mapping_set_id: int, status: str) -> MappingSetRecord:
        existing = self.get_mapping_set(mapping_set_id)
        payload = existing.model_dump(mode="json")
        payload["status"] = status
        payload.pop("mapping_set_id", None)
        with self.connection() as connection:
            connection.execute(
                "UPDATE mapping_sets SET payload = ? WHERE id = ?",
                (json.dumps(payload), mapping_set_id),
            )
        return existing.model_copy(update={"status": status})

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

    def clear_mapping_sets(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM mapping_set_audit_logs")
            connection.execute("DELETE FROM mapping_sets")

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
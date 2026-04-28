from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from contextlib import contextmanager

from app.core.config import settings
from app.models.mapping import BenchmarkDatasetRecord, DecisionLogEntry, EvaluationMetrics, EvaluationRunRecord, UserCorrectionEntry


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
            connection.execute("DELETE FROM benchmark_datasets")
            connection.execute("DELETE FROM evaluation_runs")

    def clear_decision_logs(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM decision_logs")

    def clear_user_corrections(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM user_corrections")

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


persistence_service = SQLitePersistenceService(settings.sqlite_path)
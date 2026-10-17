import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from backend.db.base import Database
from backend.models import Job
from backend.schemas import Violation

_violations = TypeAdapter(list[Violation])


class JobRepository(ABC):
    @abstractmethod
    def add(self, *, job_id: str, video_path: Path, created_at: datetime) -> Job: ...

    @abstractmethod
    def get(self, job_id: str) -> Job | None: ...

    @abstractmethod
    def complete(
        self, job_id: str, violations: list[Violation], finished_at: datetime
    ) -> None: ...

    @abstractmethod
    def fail(self, job_id: str, error: str, finished_at: datetime) -> None: ...

    @abstractmethod
    def fail_unfinished(self, error: str, finished_at: datetime) -> None: ...


class SqliteJobRepository(JobRepository):
    def __init__(self, database: Database[sqlite3.Connection]) -> None:
        self._database = database

    def add(self, *, job_id: str, video_path: Path, created_at: datetime) -> Job:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO jobs (id, status, video_path, created_at)
                VALUES (?, 'processing', ?, ?)
                RETURNING *
                """,
                (job_id, str(video_path), created_at.isoformat()),
            ).fetchone()
        return _to_model(row)

    def get(self, job_id: str) -> Job | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return _to_model(row) if row else None

    def complete(
        self, job_id: str, violations: list[Violation], finished_at: datetime
    ) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'done', violations = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    _violations.dump_json(violations).decode(),
                    finished_at.isoformat(),
                    job_id,
                ),
            )

    def fail(self, job_id: str, error: str, finished_at: datetime) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'failed', error = ?, finished_at = ?
                WHERE id = ?
                """,
                (error, finished_at.isoformat(), job_id),
            )

    def fail_unfinished(self, error: str, finished_at: datetime) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'failed', error = ?, finished_at = ?
                WHERE status = 'processing'
                """,
                (error, finished_at.isoformat()),
            )


def _to_model(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        status=row["status"],
        video_path=Path(row["video_path"]),
        violations=(
            _violations.validate_json(row["violations"])
            if row["violations"] is not None
            else None
        ),
        error=row["error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        finished_at=(
            datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
        ),
    )

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from backend.db.base import Database
from backend.models import ApiKey


class ApiKeyRepository(ABC):
    @abstractmethod
    def add(
        self,
        *,
        name: str,
        key_hash: str,
        last4: str,
        created_at: datetime,
        expires_at: datetime | None,
    ) -> ApiKey: ...

    @abstractmethod
    def get_by_hash(self, key_hash: str) -> ApiKey | None: ...

    @abstractmethod
    def list_all(self) -> list[ApiKey]: ...

    @abstractmethod
    def mark_used(self, key_id: int, used_at: datetime) -> None: ...

    @abstractmethod
    def revoke(self, key_id: int, revoked_at: datetime) -> ApiKey | None: ...


class SqliteApiKeyRepository(ApiKeyRepository):
    def __init__(self, database: Database[sqlite3.Connection]) -> None:
        self._database = database

    def add(
        self,
        *,
        name: str,
        key_hash: str,
        last4: str,
        created_at: datetime,
        expires_at: datetime | None,
    ) -> ApiKey:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO api_keys (name, key_hash, last4, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                RETURNING *
                """,
                (name, key_hash, last4, _to_text(created_at), _to_text(expires_at)),
            ).fetchone()
        return _to_model(row)

    def get_by_hash(self, key_hash: str) -> ApiKey | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)
            ).fetchone()
        return _to_model(row) if row else None

    def list_all(self) -> list[ApiKey]:
        with self._database.connect() as connection:
            rows = connection.execute("SELECT * FROM api_keys ORDER BY id").fetchall()
        return [_to_model(row) for row in rows]

    def mark_used(self, key_id: int, used_at: datetime) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (_to_text(used_at), key_id),
            )

    def revoke(self, key_id: int, revoked_at: datetime) -> ApiKey | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE api_keys SET revoked_at = COALESCE(revoked_at, ?)
                WHERE id = ?
                RETURNING *
                """,
                (_to_text(revoked_at), key_id),
            ).fetchone()
        return _to_model(row) if row else None


def _to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _to_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _to_model(row: sqlite3.Row) -> ApiKey:
    return ApiKey(
        id=row["id"],
        name=row["name"],
        key_hash=row["key_hash"],
        last4=row["last4"],
        created_at=datetime.fromisoformat(row["created_at"]),
        expires_at=_to_datetime(row["expires_at"]),
        last_used_at=_to_datetime(row["last_used_at"]),
        revoked_at=_to_datetime(row["revoked_at"]),
    )

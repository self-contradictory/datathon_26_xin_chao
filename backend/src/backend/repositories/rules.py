import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from backend.db.base import Database
from backend.models import RuleStatusChange, StoredRule
from backend.rules.models import Rule


class RuleRepository(ABC):
    @abstractmethod
    def add(self, rule: Rule, created_at: datetime, note: str | None = None) -> StoredRule: ...

    @abstractmethod
    def get(self, rule_id: str, version: str) -> StoredRule | None: ...

    @abstractmethod
    def list_all(self) -> list[StoredRule]: ...

    @abstractmethod
    def replace(self, rule: Rule, changed_at: datetime, note: str | None) -> StoredRule: ...

    @abstractmethod
    def history(self, rule_id: str) -> list[RuleStatusChange]: ...


class SqliteRuleRepository(RuleRepository):
    def __init__(self, database: Database[sqlite3.Connection]) -> None:
        self._database = database

    def add(self, rule: Rule, created_at: datetime, note: str | None = None) -> StoredRule:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO rules (rule_id, version, status, document, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING *
                """,
                (
                    rule.rule_id,
                    rule.version,
                    rule.status,
                    rule.model_dump_json(by_alias=True),
                    created_at.isoformat(),
                    created_at.isoformat(),
                ),
            ).fetchone()
            _log(connection, rule, None, created_at, note)
        return _to_model(row)

    def get(self, rule_id: str, version: str) -> StoredRule | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM rules WHERE rule_id = ? AND version = ?", (rule_id, version)
            ).fetchone()
        return _to_model(row) if row else None

    def list_all(self) -> list[StoredRule]:
        with self._database.connect() as connection:
            rows = connection.execute("SELECT * FROM rules ORDER BY rule_id, created_at").fetchall()
        return [_to_model(row) for row in rows]

    def replace(self, rule: Rule, changed_at: datetime, note: str | None) -> StoredRule:
        with self._database.connect() as connection:
            previous = connection.execute(
                "SELECT status FROM rules WHERE rule_id = ? AND version = ?",
                (rule.rule_id, rule.version),
            ).fetchone()
            row = connection.execute(
                """
                UPDATE rules SET status = ?, document = ?, updated_at = ?
                WHERE rule_id = ? AND version = ?
                RETURNING *
                """,
                (
                    rule.status,
                    rule.model_dump_json(by_alias=True),
                    changed_at.isoformat(),
                    rule.rule_id,
                    rule.version,
                ),
            ).fetchone()
            _log(connection, rule, previous["status"], changed_at, note)
        return _to_model(row)

    def history(self, rule_id: str) -> list[RuleStatusChange]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM rule_status_changes WHERE rule_id = ? ORDER BY id", (rule_id,)
            ).fetchall()
        return [
            RuleStatusChange(
                rule_id=row["rule_id"],
                version=row["version"],
                from_status=row["from_status"],
                to_status=row["to_status"],
                changed_at=datetime.fromisoformat(row["changed_at"]),
                note=row["note"],
            )
            for row in rows
        ]


def _log(
    connection: sqlite3.Connection,
    rule: Rule,
    from_status: str | None,
    changed_at: datetime,
    note: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO rule_status_changes (rule_id, version, from_status, to_status, changed_at, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (rule.rule_id, rule.version, from_status, rule.status, changed_at.isoformat(), note),
    )


def _to_model(row: sqlite3.Row) -> StoredRule:
    return StoredRule(
        rule=Rule.model_validate_json(row["document"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )

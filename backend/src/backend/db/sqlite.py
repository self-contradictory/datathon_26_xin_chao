import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from backend.db.base import Database

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class SqliteDatabase(Database[sqlite3.Connection]):
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA_PATH.read_text())

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

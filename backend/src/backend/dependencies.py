from functools import lru_cache

from backend.config import settings
from backend.db.sqlite import SqliteDatabase


@lru_cache
def get_database() -> SqliteDatabase:
    return SqliteDatabase(settings.DATABASE_PATH)

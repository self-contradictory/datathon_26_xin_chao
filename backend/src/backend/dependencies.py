from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from backend.config import settings
from backend.db.sqlite import SqliteDatabase
from backend.models import ApiKey
from backend.repositories.api_keys import ApiKeyRepository, SqliteApiKeyRepository
from backend.services.api_keys import ApiKeyService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@lru_cache
def get_database() -> SqliteDatabase:
    return SqliteDatabase(settings.DATABASE_PATH)


def get_api_key_repository(
    database: Annotated[SqliteDatabase, Depends(get_database)],
) -> ApiKeyRepository:
    return SqliteApiKeyRepository(database)


def get_api_key_service(
    repository: Annotated[ApiKeyRepository, Depends(get_api_key_repository)],
) -> ApiKeyService:
    return ApiKeyService(repository)


def require_api_key(
    key: Annotated[str | None, Depends(api_key_header)],
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> ApiKey:
    api_key = service.authenticate(key) if key else None
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "APIKey"},
        )
    return api_key

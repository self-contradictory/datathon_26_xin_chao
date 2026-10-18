from concurrent.futures import Executor, ThreadPoolExecutor
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from backend.analyzers.base import VideoAnalyzer
from backend.analyzers.questions import QuestionAnalyzer
from backend.config import settings
from backend.db.sqlite import SqliteDatabase
from backend.models import ApiKey
from backend.repositories.api_keys import ApiKeyRepository, SqliteApiKeyRepository
from backend.repositories.jobs import JobRepository, SqliteJobRepository
from backend.perception.pipeline import PerceptionReconstructor
from backend.perception.settings import load_config
from backend.reconstruction.pipeline import Reconstructor
from backend.semantic.vlm import TextVLM
from backend.services.api_keys import ApiKeyService
from backend.services.jobs import JobService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@lru_cache
def get_database() -> SqliteDatabase:
    return SqliteDatabase(settings.DATABASE_PATH)


@lru_cache
def get_analyzer() -> VideoAnalyzer:
    model = TextVLM(
        settings.MODEL, settings.MODEL_PATH, settings.MODEL_DEVICE, settings.MODEL_QUANTIZATION,
        cache_dir=settings.TIMELINE_DIR.parent / "model_calls", call_seconds=settings.FOLLOWUP_CALL_SECONDS,
    )
    reconstructor = (
        PerceptionReconstructor(model, load_config(model.name), settings.POSE_DEVICE) if settings.PERCEPTION
        else Reconstructor(model, settings.SAMPLE_FPS, settings.IMAGE_TOKENS)
    )
    return QuestionAnalyzer(
        reconstructor, settings.RULE_MODE,
        settings.FOLLOWUP_MAX_CALLS, settings.FOLLOWUP_MAX_FRAMES, settings.TIMELINE_DIR,
        settings.TEMPORAL_SCAN,
    )


@lru_cache
def get_job_executor() -> Executor:
    return ThreadPoolExecutor(max_workers=settings.JOB_WORKERS)


def get_api_key_repository(
    database: Annotated[SqliteDatabase, Depends(get_database)],
) -> ApiKeyRepository:
    return SqliteApiKeyRepository(database)


def get_api_key_service(
    repository: Annotated[ApiKeyRepository, Depends(get_api_key_repository)],
) -> ApiKeyService:
    return ApiKeyService(repository)


def get_job_repository(
    database: Annotated[SqliteDatabase, Depends(get_database)],
) -> JobRepository:
    return SqliteJobRepository(database)


def get_job_service(
    repository: Annotated[JobRepository, Depends(get_job_repository)],
    analyzer: Annotated[VideoAnalyzer, Depends(get_analyzer)],
    executor: Annotated[Executor, Depends(get_job_executor)],
) -> JobService:
    return JobService(repository, analyzer, executor, settings.UPLOAD_DIR)


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

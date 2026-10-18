import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import router
from backend.config import settings
from backend.dependencies import (
    get_analyzer,
    get_api_key_repository,
    get_api_key_service,
    get_database,
    get_job_executor,
    get_job_repository,
    get_job_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("backend").setLevel(logging.INFO)
    logger = logging.getLogger(__name__)
    database = get_database()
    database.initialize()
    get_api_key_service(get_api_key_repository(database)).sync(settings.API_KEYS)
    executor = get_job_executor()
    logger.info(
        "Loading model=%s device=%s quantization=%s; sample_fps=%s image_tokens=%s "
        "temporal_scan=%s followup_max_calls=%s workers=%s",
        settings.MODEL, settings.MODEL_DEVICE or "auto", settings.MODEL_QUANTIZATION,
        settings.SAMPLE_FPS, settings.IMAGE_TOKENS, settings.TEMPORAL_SCAN,
        settings.FOLLOWUP_MAX_CALLS, settings.JOB_WORKERS,
    )
    get_job_service(
        get_job_repository(database), get_analyzer(), executor
    ).fail_unfinished()
    logger.info("Model loaded; ready to analyze videos")
    yield
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="Xin Chao", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


def main() -> None:
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)

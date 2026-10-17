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
    database = get_database()
    database.initialize()
    get_api_key_service(get_api_key_repository(database)).sync(settings.API_KEYS)
    executor = get_job_executor()
    get_job_service(
        get_job_repository(database), get_analyzer(), executor
    ).fail_unfinished()
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

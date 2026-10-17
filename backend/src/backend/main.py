from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from backend.api import router
from backend.config import settings
from backend.dependencies import get_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    get_database().initialize()
    yield


app = FastAPI(title="Xin Chao", lifespan=lifespan)
app.include_router(router)


def main() -> None:
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)

import uvicorn
from fastapi import FastAPI

from backend.api import router
from backend.config import settings

app = FastAPI(title="Xin Chao")
app.include_router(router)


def main() -> None:
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)

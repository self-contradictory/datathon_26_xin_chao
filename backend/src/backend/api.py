from fastapi import APIRouter, Depends, UploadFile

from backend.dependencies import require_api_key

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


@router.post("/analyze")
async def analyze(file: UploadFile):
    ...


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    ...

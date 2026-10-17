from fastapi import APIRouter, UploadFile

router = APIRouter(prefix="/api/v1")


@router.post("/analyze")
async def analyze(file: UploadFile):
    ...


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    ...

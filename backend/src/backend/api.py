from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from backend.dependencies import get_job_service, require_api_key
from backend.schemas import AnalyzeResponse, JobResponse
from backend.services.jobs import InvalidVideoError, JobNotFoundError, JobService

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


@router.post("/analyze")
def analyze(
    file: UploadFile,
    service: Annotated[JobService, Depends(get_job_service)],
) -> AnalyzeResponse:
    try:
        job = service.submit(file.file)
    except InvalidVideoError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    return AnalyzeResponse(job_id=job.id)


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    try:
        job = service.get(job_id)
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    return JobResponse(
        job_id=job.id,
        status=job.status,
        verdict=job.verdict,
        violations=job.violations,
        error=job.error,
    )

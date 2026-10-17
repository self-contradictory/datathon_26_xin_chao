import logging
import shutil
from concurrent.futures import Executor
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from backend.analyzers.base import VideoAnalyzer
from backend.models import Job
from backend.repositories.jobs import JobRepository

logger = logging.getLogger(__name__)


class JobNotFoundError(LookupError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job {job_id} not found")
        self.job_id = job_id


class JobService:
    def __init__(
        self,
        repository: JobRepository,
        analyzer: VideoAnalyzer,
        executor: Executor,
        upload_dir: Path,
    ) -> None:
        self._repository = repository
        self._analyzer = analyzer
        self._executor = executor
        self._upload_dir = upload_dir

    def submit(self, video: BinaryIO) -> Job:
        job_id = uuid4().hex
        video_path = self._upload_dir / f"{job_id}.mov"
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        with video_path.open("wb") as file:
            shutil.copyfileobj(video, file)
        job = self._repository.add(
            job_id=job_id, video_path=video_path, created_at=datetime.now(UTC)
        )
        self._executor.submit(self._run, job)
        return job

    def get(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def fail_unfinished(self) -> None:
        self._repository.fail_unfinished(
            "Server restarted before the job finished", datetime.now(UTC)
        )

    def _run(self, job: Job) -> None:
        try:
            violations = self._analyzer.analyze(job.video_path)
            self._repository.complete(job.id, violations, datetime.now(UTC))
        except Exception as error:
            logger.exception("Job %s failed", job.id)
            self._repository.fail(job.id, str(error), datetime.now(UTC))

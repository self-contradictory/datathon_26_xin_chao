import logging
import shutil
from concurrent.futures import Executor
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import BinaryIO
from uuid import uuid4

import cv2

from backend.analyzers.base import VideoAnalyzer
from backend.models import Job
from backend.repositories.jobs import JobRepository

logger = logging.getLogger(__name__)


class JobNotFoundError(LookupError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job {job_id} not found")
        self.job_id = job_id


class InvalidVideoError(ValueError):
    pass


def readable_video(path: Path) -> bool:
    capture = cv2.VideoCapture(str(path))
    try:
        ok, _ = capture.read()
        return ok
    finally:
        capture.release()


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
        if not readable_video(video_path):
            empty = video_path.stat().st_size == 0
            video_path.unlink(missing_ok=True)
            raise InvalidVideoError("The uploaded file is empty" if empty else "The uploaded file is not a readable video")
        job = self._repository.add(
            job_id=job_id, video_path=video_path, created_at=datetime.now(UTC)
        )
        logger.info("Job %s queued (%s bytes)", job.id, video_path.stat().st_size)
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
        started = perf_counter()
        logger.info(
            "Job %s started after %.1fs in queue", job.id,
            (datetime.now(UTC) - job.created_at).total_seconds(),
        )
        try:
            violations = self._analyzer.analyze(job.video_path)
            self._repository.complete(job.id, violations, datetime.now(UTC))
            logger.info(
                "Job %s completed in %.1fs (%s findings)",
                job.id, perf_counter() - started, len(violations),
            )
        except Exception as error:
            logger.exception("Job %s failed", job.id)
            self._repository.fail(job.id, str(error), datetime.now(UTC))

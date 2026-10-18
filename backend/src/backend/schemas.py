from typing import Literal

from pydantic import BaseModel, Field

type JobStatus = Literal["processing", "done", "failed"]
type Verdict = Literal["no_violation", "violation"]


class EvidenceFrame(BaseModel):
    timestamp_sec: float
    image_base64: str


class Violation(BaseModel):
    type: str
    timecode_sec: float
    description: str
    evidence_frames: list[EvidenceFrame] = Field(min_length=1, max_length=3)


class AnalyzeResponse(BaseModel):
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    verdict: Verdict | None = None
    violations: list[Violation] | None = None
    error: str | None = None

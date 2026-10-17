from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from backend.schemas import JobStatus, Verdict, Violation

type ApiKeyStatus = Literal["active", "expired", "revoked"]


@dataclass(frozen=True, slots=True)
class ApiKey:
    id: int
    name: str
    key_hash: str
    last4: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None

    def status(self, now: datetime) -> ApiKeyStatus:
        if self.revoked_at is not None:
            return "revoked"
        if self.expires_at is not None and self.expires_at <= now:
            return "expired"
        return "active"


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    status: JobStatus
    video_path: Path
    violations: list[Violation] | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None

    @property
    def verdict(self) -> Verdict | None:
        if self.violations is None:
            return None
        return "violation" if self.violations else "no_violation"

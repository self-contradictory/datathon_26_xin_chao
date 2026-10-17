from dataclasses import dataclass
from datetime import datetime
from typing import Literal

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

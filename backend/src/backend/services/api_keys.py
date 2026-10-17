import hashlib
import secrets
import string
from dataclasses import replace
from datetime import UTC, datetime

from backend.models import ApiKey
from backend.repositories.api_keys import ApiKeyRepository


class ApiKeyNotFoundError(LookupError):
    def __init__(self, key_id: int) -> None:
        super().__init__(f"API key {key_id} not found")
        self.key_id = key_id


class ApiKeyService:
    PREFIX = "xc_"
    ALPHABET = string.ascii_letters + string.digits
    SECRET_LENGTH = 43

    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repository = repository

    def create(self, name: str, expires_at: datetime | None = None) -> tuple[ApiKey, str]:
        secret = "".join(secrets.choice(self.ALPHABET) for _ in range(self.SECRET_LENGTH))
        key = self.PREFIX + secret
        api_key = self._repository.add(
            name=name,
            key_hash=self._hash(key),
            last4=key[-4:],
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        return api_key, key

    def authenticate(self, key: str) -> ApiKey | None:
        if not key.startswith(self.PREFIX):
            return None
        api_key = self._repository.get_by_hash(self._hash(key))
        now = datetime.now(UTC)
        if api_key is None or api_key.status(now) != "active":
            return None
        self._repository.mark_used(api_key.id, now)
        return replace(api_key, last_used_at=now)

    def list_keys(self) -> list[ApiKey]:
        return self._repository.list_all()

    def revoke(self, key_id: int) -> ApiKey:
        api_key = self._repository.revoke(key_id, datetime.now(UTC))
        if api_key is None:
            raise ApiKeyNotFoundError(key_id)
        return api_key

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

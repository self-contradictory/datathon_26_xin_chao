from datetime import UTC, datetime

from backend.models import RuleStatusChange, StoredRule
from backend.repositories.rules import RuleRepository
from backend.rules.findings import Mode
from backend.rules.models import Rule, RuleRegistry, RuleStatus
from backend.rules.registry import version_key


class RuleRegistryService:
    def __init__(self, repository: RuleRepository) -> None:
        self._repository = repository

    def publish(self, rule: Rule, note: str | None = None) -> StoredRule:
        existing = self._repository.get(rule.rule_id, rule.version)
        if existing is not None:
            if _content(existing.rule) == _content(rule):
                return existing
            raise ValueError(
                f"Rule {rule.rule_id} version {rule.version} is already stored with different "
                "content; publish it under a new version"
            )
        now = datetime.now(UTC)
        if rule.status != "active":
            return self._repository.add(rule, now, note)
        stored = self._repository.add(rule.model_copy(update={"status": "candidate"}), now, note)
        return self.set_status(stored.rule.rule_id, stored.rule.version, "active", note)

    def import_registry(self, registry: RuleRegistry, note: str | None = None) -> list[StoredRule]:
        return [self.publish(rule, note) for rule in registry.rules]

    def get(self, rule_id: str, version: str) -> StoredRule:
        stored = self._repository.get(rule_id, version)
        if stored is None:
            raise LookupError(f"Rule {rule_id} version {version} not found")
        return stored

    def list_all(self) -> list[StoredRule]:
        return self._repository.list_all()

    def history(self, rule_id: str) -> list[RuleStatusChange]:
        return self._repository.history(rule_id)

    def set_status(
        self, rule_id: str, version: str, status: RuleStatus, note: str | None = None
    ) -> StoredRule:
        stored = self.get(rule_id, version)
        current = stored.rule.status
        if status == current:
            return stored
        updated = stored.rule.model_copy(update={"status": status})
        now = datetime.now(UTC)
        if status == "active":
            for other in self._repository.list_all():
                if other.rule.rule_id == rule_id and other.rule.status == "active":
                    deprecated = other.rule.model_copy(update={"status": "deprecated"})
                    self._repository.replace(deprecated, now, f"superseded by {version}")
        return self._repository.replace(updated, now, note)

    def rules(self, mode: Mode) -> list[Rule]:
        statuses: tuple[RuleStatus, ...] = ("active",) if mode == "production" else ("active", "candidate")
        newest: dict[tuple[str, RuleStatus], Rule] = {}
        for stored in self._repository.list_all():
            rule = stored.rule
            key = (rule.rule_id, rule.status)
            if rule.status in statuses and (
                key not in newest or version_key(rule.version) > version_key(newest[key].version)
            ):
                newest[key] = rule
        return [newest[key] for key in sorted(newest)]


def _content(rule: Rule) -> dict:
    return rule.model_dump(mode="json", by_alias=True, exclude={"status"})

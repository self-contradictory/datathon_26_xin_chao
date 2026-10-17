import re
from pathlib import Path

import yaml

from backend.rules.models import RuleRegistry

DEFAULT_REGISTRY = Path(__file__).with_name("cashdesk.yaml")


def load_registry(path: Path = DEFAULT_REGISTRY) -> RuleRegistry:
    return RuleRegistry.model_validate(yaml.safe_load(path.read_text()))


def version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"[.\-+]", version)
    )

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from backend.rules.findings import Outcome, UnknownKind
from backend.rules.index import Bounds, Evidence, Piece, Truth
from backend.steg import Event, ProcedureEpisode


TRIGGER_ENTITY = "$trigger_entity"


type Quantifier = Callable[[Sequence[Piece]], Truth]


type Failures = dict[str, tuple[UnknownKind, str]]


class Undetermined(Exception):
    def __init__(self, kind: UnknownKind, reason: str) -> None:
        super().__init__(reason)
        self.kind: UnknownKind = kind
        self.reason = reason


@dataclass(slots=True)
class Context:
    episode: ProcedureEpisode | None
    window: tuple[float, float]
    values: dict[str, str]
    failures: Failures
    pool: list[Event]


@dataclass(slots=True)
class Trigger:
    ref: str
    bounds: Bounds
    values: dict[str, str]
    failures: Failures
    evidence: Evidence
    weak: str | None = None
    event: Event | None = None
    episode: ProcedureEpisode | None = None


@dataclass(slots=True)
class Check:
    truth: Truth
    reason: str
    kind: UnknownKind | None = None
    evidence: Evidence = field(default_factory=Evidence)
    values: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Decision:
    outcome: Outcome
    reason: str
    kind: UnknownKind | None = None
    time: float | None = None
    span: tuple[float, float] | None = None
    evidence: Evidence = field(default_factory=Evidence)
    details: list[str] = field(default_factory=list)
    bindings: dict[str, str] = field(default_factory=dict)


def unknown(kind: UnknownKind, reason: str, **extra) -> Decision:
    return Decision("UNKNOWN", reason, kind, **extra)


def format_time(time: float) -> str:
    return f"{time:.1f}s"


def first_unknown(checks: Iterable[Check]) -> tuple[UnknownKind, str]:
    for check in checks:
        if check.truth == "UNKNOWN":
            return check.kind or "uncertain_state", check.reason
    return "uncertain_state", "the evidence is inconclusive"

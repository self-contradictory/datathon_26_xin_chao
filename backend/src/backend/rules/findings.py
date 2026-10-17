from typing import Literal

from pydantic import BaseModel, Field

from backend.rules.models import RuleStatus, RuleType, Source

type Outcome = Literal["VIOLATION", "CLEAR", "UNKNOWN", "NOT_APPLICABLE"]
type Mode = Literal["production", "shadow"]
type UnknownKind = Literal[
    "not_observed",
    "incomplete_episode",
    "missing_binding",
    "ambiguous_role",
    "uncertain_state",
    "uncertain_order",
    "weak_evidence",
    "no_track",
    "critical_quality_flag",
    "unsupported",
]

SEVERITY: dict[Outcome, int] = {"VIOLATION": 3, "UNKNOWN": 2, "CLEAR": 1, "NOT_APPLICABLE": 0}


class FrameRef(BaseModel):
    id: str
    timestamp_sec: float


class Finding(BaseModel):
    rule_id: str
    rule_version: str
    rule_type: RuleType
    rule_status: RuleStatus
    name: str
    category: str
    production: bool
    outcome: Outcome
    unknown_kind: UnknownKind | None = None
    reason: str
    details: list[str] = Field(default_factory=list)
    timecode_sec: float
    start_sec: float
    end_sec: float
    trigger_id: str
    episode_id: str | None = None
    bindings: dict[str, str] = Field(default_factory=dict)
    event_ids: list[str] = Field(default_factory=list)
    state_track_ids: list[str] = Field(default_factory=list)
    relation_track_ids: list[str] = Field(default_factory=list)
    episode_ids: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    quality_flag_ids: list[str] = Field(default_factory=list)
    evidence_frames: list[FrameRef] = Field(default_factory=list, max_length=3)
    source: Source


class RuleEvaluation(BaseModel):
    rule_id: str
    version: str
    status: RuleStatus
    type: RuleType
    findings: list[Finding]

    @property
    def outcome(self) -> Outcome:
        if not self.findings:
            return "NOT_APPLICABLE"
        return max((finding.outcome for finding in self.findings), key=SEVERITY.__getitem__)


class EvaluationReport(BaseModel):
    video_id: str
    registry_id: str | None
    mode: Mode
    rules: list[RuleEvaluation]

    def findings(self, *outcomes: Outcome) -> list[Finding]:
        found = [finding for rule in self.rules for finding in rule.findings]
        if outcomes:
            found = [finding for finding in found if finding.outcome in outcomes]
        return sorted(found, key=lambda finding: (finding.timecode_sec, finding.rule_id))

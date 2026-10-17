from typing import Literal, Protocol

import numpy as np
from pydantic import BaseModel, Field

from backend.rules.models import Matcher
from backend.steg import Entity, Participant


class TimeWindow(BaseModel):
    relation: Literal["at", "during", "before", "after", "between", "until", "range"]
    start_sec: float
    end_sec: float
    anchor_ids: list[str] = Field(default_factory=list)


class EvidenceQuestion(BaseModel):
    id: str
    rule_id: str
    matcher: Matcher
    window: TimeWindow
    bindings: dict[str, str] = Field(default_factory=dict)
    episode_id: str | None = None
    reason: str


class FrameFact(BaseModel):
    kind: Literal["state", "relation"] = "state"
    frame_id: str
    subject_id: str
    predicate: str
    value: str | None = None
    object_entity_id: str | None = None
    visibility: Literal["clear", "partial", "occluded", "unknown"]
    reliability: Literal["high", "medium", "low"]


class ObservedAction(BaseModel):
    action: str
    first_frame_id: str
    last_frame_id: str
    participants: list[Participant]
    evidence_frame_ids: list[str]
    reliability: Literal["high", "medium", "low"]
    description: str


class VisualAnswer(BaseModel):
    status: Literal["observed", "uncertain", "not_visible"]
    entities: list[Entity] = Field(default_factory=list)
    facts: list[FrameFact] = Field(default_factory=list)
    actions: list[ObservedAction] = Field(default_factory=list)
    explanation: str


class SemanticDecision(BaseModel):
    record_index: int = Field(ge=0)
    requirement_index: int = Field(ge=0)
    supports: bool | None
    equivalent: bool = False
    reason: str


class SemanticAnswer(BaseModel):
    matches: list[SemanticDecision] = Field(default_factory=list)


class FollowupRecord(BaseModel):
    question: EvidenceQuestion
    answer: VisualAnswer | None = None
    error: str | None = None


class StructuredModel(Protocol):
    def structured[T: BaseModel](
        self, prompt: str, schema: type[T], images: list[np.ndarray] | None = None,
        image_tokens: int = 256, max_new_tokens: int = 1024,
    ) -> T: ...

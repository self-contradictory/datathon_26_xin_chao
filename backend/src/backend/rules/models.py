from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

type Identifier = Annotated[str, Field(min_length=1)]
type Variable = Annotated[str, Field(pattern=r"^\$[A-Za-z_][A-Za-z_0-9]*$")]
type RuleType = Literal[
    "FORBIDDEN",
    "REQUIRED_ACTION",
    "PRECEDENCE",
    "DURING",
    "STATE_INVARIANT",
    "CONDITIONAL",
    "TIMEOUT",
    "CARDINALITY",
    "MUTUAL_EXCLUSION",
    "ROLE_RELATION",
    "SEPARATION",
    "PROCEDURE",
]
type RuleStatus = Literal["candidate", "active", "disabled", "deprecated"]


class _RuleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @model_serializer(mode="wrap")
    def serialize_present_fields(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        fields = type(self).model_fields
        present = set(self.model_fields_set)
        present.update(fields[name].alias or name for name in self.model_fields_set)
        return {name: value for name, value in handler(self).items() if name in present}


class EntityByKind(_RuleModel):
    kind: Literal["person", "object", "zone"]
    subtype: Identifier


class EntityByEpisodeRole(_RuleModel):
    episode_role: Identifier


type EntitySelector = Variable | EntityByKind | EntityByEpisodeRole


class EventMatcher(_RuleModel):
    kind: Literal["event"]
    action: Identifier
    participants: dict[Identifier, Variable] | None = None


class StateMatcher(_RuleModel):
    kind: Literal["state"]
    property: Identifier
    entity: EntitySelector
    value: Literal["true", "false"]
    knowledge: Literal["bounded_by_observations"] | None = None


class RelationMatcher(_RuleModel):
    kind: Literal["relation"]
    relation: Identifier
    subject: EntitySelector
    target: EntitySelector
    knowledge: Literal["bounded_by_observations"] | None = None


class EpisodeMatcher(_RuleModel):
    kind: Literal["episode"]
    episode_kind: Identifier


class EpisodeEndMatcher(_RuleModel):
    kind: Literal["episode_end"]
    requires_end_boundary: Literal["observed"]


type Matcher = Annotated[
    EventMatcher | StateMatcher | RelationMatcher | EpisodeMatcher | EpisodeEndMatcher,
    Field(discriminator="kind"),
]


class VideoScope(_RuleModel):
    kind: Literal["video"]


class EpisodeScope(_RuleModel):
    kind: Literal["episode"]
    episode_kind: Identifier
    bind: Variable
    episode_roles: dict[Identifier, Variable] | None = None


type Scope = Annotated[VideoScope | EpisodeScope, Field(discriminator="kind")]


class Source(_RuleModel):
    kind: Literal["regulatory_candidate", "hypothetical", "internal_policy"]
    document: Identifier
    clause: str | None
    url: str | None
    verified: bool
    note: str


class EvidencePolicy(_RuleModel):
    allow_hypotheses: bool
    allow_disputed: bool
    negative_evidence: Literal["requires_explicit_bounded_false_or_proven_completeness"]
    on_missing_binding: Literal["UNKNOWN"]
    on_ambiguous_role: Literal["UNKNOWN"]
    on_incomplete_episode: Literal["UNKNOWN"]
    max_evidence_frames: Annotated[int, Field(ge=1, le=3)]
    required_verification: Literal["human_confirmed"] | None = None


class ForbiddenLogic(_RuleModel):
    type: Literal["FORBIDDEN"]
    when_all: list[Matcher]
    at: Literal["trigger_start"]


class RequiredActionLogic(_RuleModel):
    type: Literal["REQUIRED_ACTION"]
    must: EventMatcher
    deadline: EpisodeEndMatcher
    order: Literal["after_trigger_before_boundary"]


class PrecedenceLogic(_RuleModel):
    type: Literal["PRECEDENCE"]
    must_precede: EventMatcher
    before: EventMatcher
    order: Literal["after_trigger_before_boundary"]


class DuringLogic(_RuleModel):
    type: Literal["DURING"]
    required: StateMatcher
    interval: Literal["entire_trigger_interval"]


class StateInvariantLogic(_RuleModel):
    type: Literal["STATE_INVARIANT"]
    required: StateMatcher
    until: EventMatcher
    window: Literal["after_trigger_until_boundary"]


class ConditionalLogic(_RuleModel):
    type: Literal["CONDITIONAL"]
    if_all: Annotated[list[Matcher], Field(min_length=1)]
    then: Literal["FORBIDDEN"]
    otherwise: Literal["NOT_APPLICABLE"]


class TimeoutLogic(_RuleModel):
    type: Literal["TIMEOUT"]
    must: EventMatcher
    within_seconds: Annotated[float, Field(gt=0)]
    start_anchor: Literal["trigger_end"]


class CashierFrom(_RuleModel):
    event_action: Identifier
    participant_role: Identifier


class CardinalityLogic(_RuleModel):
    type: Literal["CARDINALITY"]
    count: EpisodeMatcher
    group_by: Literal["cashier"]
    cashier_from: CashierFrom
    max_concurrent: Annotated[int, Field(ge=1)]


class MutualExclusionLogic(_RuleModel):
    type: Literal["MUTUAL_EXCLUSION"]
    other: StateMatcher
    relation: Literal["overlaps"]


class RoleRelationLogic(_RuleModel):
    type: Literal["ROLE_RELATION"]
    all_of: Annotated[list[Matcher], Field(min_length=1)]
    at: Literal["trigger_start"]


class EpisodeOrigin(_RuleModel):
    kind: Literal["episode_membership_via_cash_received"]
    event_action: Identifier
    bundle_participant_role: Identifier


class SeparationLogic(_RuleModel):
    type: Literal["SEPARATION"]
    origin: EpisodeOrigin
    require_distinct_origin_episodes: Literal[True]


class Step(_RuleModel):
    id: Identifier
    required: bool
    any_of: Annotated[list[EventMatcher], Field(min_length=1)]
    omission_observability: (
        Literal["external_or_positively_verified_coverage", "positively_verified_coverage"]
        | None
    ) = None
    while_: list[StateMatcher] | None = Field(default=None, alias="while")


class OrderConstraint(_RuleModel):
    before: Identifier
    after: Identifier


class ProcedureLogic(_RuleModel):
    type: Literal["PROCEDURE"]
    steps: Annotated[list[Step], Field(min_length=1)]
    order_constraints: list[OrderConstraint]
    end_boundary: Literal["observed"]
    step_absence_default: Literal["UNKNOWN_unless_negation_proven"]


type RuleLogic = Annotated[
    ForbiddenLogic
    | RequiredActionLogic
    | PrecedenceLogic
    | DuringLogic
    | StateInvariantLogic
    | ConditionalLogic
    | TimeoutLogic
    | CardinalityLogic
    | MutualExclusionLogic
    | RoleRelationLogic
    | SeparationLogic
    | ProcedureLogic,
    Field(discriminator="type"),
]


class Rule(_RuleModel):
    rule_id: Identifier
    version: Identifier
    status: RuleStatus
    type: RuleType
    name: Identifier
    category: Identifier
    source: Source
    scope: Scope
    trigger: Matcher
    logic: RuleLogic
    evidence_policy: EvidencePolicy
    dataset_examples: list[Identifier]
    implementation_note: str


class RuleRegistry(_RuleModel):
    schema_version: Literal["steg-rule-dsl/1.0.0"]
    required_steg_schema_version: Literal["1.0.0"]
    registry_id: Identifier
    rules: Annotated[list[Rule], Field(min_length=1)]

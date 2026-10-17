from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
)

type Identifier = Annotated[str, Field(min_length=1)]
type Timestamp = Annotated[float, Field(ge=0)]
type PositiveNumber = Annotated[float, Field(gt=0)]
type Coordinate = Annotated[float, Field(ge=0, le=1)]
type BoundingBox = tuple[Coordinate, Coordinate, Coordinate, Coordinate]
type Visibility = Literal["clear", "partial", "occluded", "unknown"]
type Knowledge = Literal["bounded_by_observations", "extrapolated", "unknown"]


class _STEGModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @model_serializer(mode="wrap")
    def serialize_present_fields(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        return {
            name: value
            for name, value in handler(self).items()
            if name in self.model_fields_set
        }


class Video(_STEGModel):
    id: Identifier
    source_ref: Identifier
    duration_sec: PositiveNumber
    time_unit: Literal["seconds_from_start"]
    has_audio_used: Literal[False]
    width_px: Annotated[int, Field(ge=1)] | None = None
    height_px: Annotated[int, Field(ge=1)] | None = None
    nominal_fps: PositiveNumber | None = None


class Processing(_STEGModel):
    observer_model: Identifier
    observer_version: Identifier
    scan_sample_fps: PositiveNumber
    window_sec: PositiveNumber
    stride_sec: PositiveNumber
    runtime_local: Literal[True]
    replay_sample_fps: PositiveNumber | None = None
    pipeline_version: Identifier | None = None


class EvidenceFrame(_STEGModel):
    id: Identifier
    timestamp_sec: Timestamp
    source_ref: Identifier
    original_frame_index: Annotated[int, Field(ge=0)] | None = None
    roi_xyxy_normalized: BoundingBox | None = None
    stored_image_ref: Identifier | None = None

    @field_validator("roi_xyxy_normalized", mode="before")
    @classmethod
    def accept_json_box(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value


class Entity(_STEGModel):
    id: Identifier
    kind: Literal["person", "object", "zone"]
    subtype: Identifier
    identity_status: Literal["stable", "provisional", "ambiguous"]
    role: str | None = None
    role_support_observation_ids: list[Identifier] | None = None
    notes: str | None = None


class SpatialGrounding(_STEGModel):
    frame_id: Identifier
    subject_bbox_xyxy_normalized: BoundingBox | None = None
    object_bbox_xyxy_normalized: BoundingBox | None = None

    @field_validator(
        "subject_bbox_xyxy_normalized", "object_bbox_xyxy_normalized", mode="before"
    )
    @classmethod
    def accept_json_box(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value


class Observation(_STEGModel):
    id: Identifier
    timestamp_sec: Timestamp
    subject_id: Identifier
    predicate: Identifier
    visibility: Visibility
    evidence_frame_ids: Annotated[list[Identifier], Field(min_length=1)]
    source_stage: Literal["coarse_vlm", "replay_vlm", "detector", "human_annotation"]
    reliability: Literal["high", "medium", "low"]
    value: Identifier | None = None
    object_entity_id: Identifier | None = None
    spatial_grounding: list[SpatialGrounding] | None = None
    uncertain_fields: list[Identifier] | None = None
    notes: str | None = None


class Participant(_STEGModel):
    role: Identifier
    entity_id: Identifier


class _Interval(_STEGModel):
    start_sec: Timestamp
    end_sec: Timestamp


class TimeSpan(_Interval):
    start_uncertainty_sec: Timestamp | None = None
    end_uncertainty_sec: Timestamp | None = None


class Event(_STEGModel):
    id: Identifier
    action: Identifier
    time: TimeSpan
    participants: Annotated[list[Participant], Field(min_length=1)]
    support_observation_ids: Annotated[list[Identifier], Field(min_length=1)]
    evidence_frame_ids: Annotated[list[Identifier], Field(min_length=1)]
    inference_status: Literal[
        "directly_observed", "inferred_from_observations", "hypothesis"
    ]
    verification_status: Literal["first_pass", "replayed", "human_confirmed", "disputed"]
    uncertain_fields: list[Identifier] | None = None
    note: str | None = None


class StateInterval(_Interval):
    value: str | None
    knowledge: Knowledge
    support_observation_ids: list[Identifier]
    note: str | None = None


class RelationInterval(_Interval):
    target_status: Literal["known_entity", "known_none", "unknown"]
    target_entity_id: str | None
    knowledge: Knowledge
    support_observation_ids: list[Identifier]
    note: str | None = None


class StateTrack(_STEGModel):
    id: Identifier
    entity_id: Identifier
    property: Identifier
    intervals: Annotated[list[StateInterval], Field(min_length=1)]


class RelationTrack(_STEGModel):
    id: Identifier
    subject_id: Identifier
    relation: Identifier
    intervals: Annotated[list[RelationInterval], Field(min_length=1)]


class ScanWindow(_Interval):
    id: Identifier
    status: Literal["processed", "failed", "partial"]
    sampled_frame_ids: list[Identifier]
    note: str | None = None


class VisibilityInterval(_Interval):
    entity_id: Identifier
    status: Literal[
        "sampled_visible",
        "partially_occluded",
        "occluded",
        "out_of_frame",
        "not_sampled",
        "unknown",
    ]
    frame_ids: list[Identifier]
    note: str | None = None


class ObservationCoverage(_STEGModel):
    scan_windows: Annotated[list[ScanWindow], Field(min_length=1)]
    entity_visibility_intervals: list[VisibilityInterval]


class ProcedureEpisode(_STEGModel):
    id: Identifier
    kind: Identifier
    start_sec: Timestamp
    end_sec: Timestamp | None
    end_boundary_status: Literal["observed", "inferred", "unknown"]
    event_ids: list[Identifier]
    basis_observation_ids: list[Identifier]
    note: str | None = None


class QualityFlag(_STEGModel):
    id: Identifier
    kind: Literal[
        "inconsistent_evidence",
        "identity_ambiguity",
        "temporal_ambiguity",
        "coverage_gap",
        "needs_replay",
        "schema_warning",
    ]
    severity: Literal["info", "warning", "critical"]
    reference_ids: list[Identifier]
    note: Identifier


class SemanticSupport(_STEGModel):
    record_id: Identifier
    kind: Literal["action", "state", "relation", "entity", "role", "episode"]
    observed: Identifier
    requirement: Identifier
    supports: bool | None
    reason: str


class SparseTemporalEvidenceGraph(_STEGModel):
    schema_version: Literal["1.0.0"]
    video: Video
    processing: Processing
    evidence_frames: list[EvidenceFrame]
    entities: list[Entity]
    observations: list[Observation]
    events: list[Event]
    state_tracks: list[StateTrack]
    relation_tracks: list[RelationTrack]
    observation_coverage: ObservationCoverage
    procedure_episodes: list[ProcedureEpisode]
    quality_flags: list[QualityFlag]
    semantic_supports: list[SemanticSupport] = Field(default_factory=list)

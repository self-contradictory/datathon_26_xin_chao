from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from backend.steg import (
    Entity,
    Event,
    Observation,
    ProcedureEpisode,
    QualityFlag,
    RelationInterval,
    RelationTrack,
    SparseTemporalEvidenceGraph,
    StateInterval,
    StateTrack,
)

type Truth = Literal["TRUE", "FALSE", "UNKNOWN"]
type PieceStatus = Literal["match", "contradict", "unknown"]
type RoleProblem = Literal["missing_binding", "ambiguous_role"]

EPSILON = 1e-6
OPPOSITE = {"true": "false", "false": "true"}
VERIFIED_STAGES = frozenset({"replay_vlm", "human_annotation"})


def conjunction(values: Iterable[Truth]) -> Truth:
    values = list(values)
    if "FALSE" in values:
        return "FALSE"
    return "TRUE" if all(value == "TRUE" for value in values) else "UNKNOWN"


def disjunction(values: Iterable[Truth]) -> Truth:
    values = list(values)
    if "TRUE" in values:
        return "TRUE"
    return "FALSE" if values and all(value == "FALSE" for value in values) else "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Bounds:

    start: float
    end: float
    earliest_start: float
    latest_start: float
    earliest_end: float
    latest_end: float

    @classmethod
    def exact(cls, start: float, end: float) -> Bounds:
        return cls(start, end, start, start, end, end)

    @classmethod
    def of_event(cls, event: Event, duration: float) -> Bounds:
        time = event.time
        before = max(0.0, time.start_sec - (time.start_uncertainty_sec or 0.0))
        after = min(duration, time.end_sec + (time.end_uncertainty_sec or 0.0))
        if time.end_sec > time.start_sec:
            return cls(time.start_sec, time.end_sec, before, time.start_sec, time.end_sec, after)
        return cls(time.start_sec, time.end_sec, before, after, before, after)

    @property
    def certain(self) -> tuple[float, float] | None:
        if self.latest_start <= self.earliest_end + EPSILON:
            return self.latest_start, max(self.latest_start, self.earliest_end)
        return None

    @property
    def possible(self) -> tuple[float, float]:
        return self.earliest_start, self.latest_end

    @property
    def start_window(self) -> tuple[float, float]:
        return self.earliest_start, self.latest_start

    @property
    def end_window(self) -> tuple[float, float]:
        return self.earliest_end, self.latest_end


def precedes(first: Bounds, second: Bounds) -> Truth:
    if first.latest_end <= second.earliest_start + EPSILON:
        return "TRUE"
    if second.latest_end <= first.earliest_start + EPSILON:
        return "FALSE"
    return "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Piece:

    start: float
    end: float
    status: PieceStatus
    support: tuple[str, ...] = ()
    target: str | None = None

    @property
    def is_point(self) -> bool:
        return self.end - self.start <= EPSILON


def matching_runs(pieces: list[Piece]) -> list[list[Piece]]:
    runs: list[list[Piece]] = []
    for piece in pieces:
        if piece.status != "match":
            continue
        if runs and piece.start <= runs[-1][-1].end + EPSILON:
            runs[-1].append(piece)
        else:
            runs.append([piece])
    return runs


def throughout(pieces: Sequence[Piece]) -> Truth:
    if any(piece.status == "contradict" for piece in pieces):
        return "FALSE"
    spans = [piece for piece in pieces if not piece.is_point] or list(pieces)
    return "TRUE" if spans and all(piece.status == "match" for piece in spans) else "UNKNOWN"


def at_instant(pieces: Sequence[Piece]) -> Truth:
    spans = [piece for piece in pieces if not piece.is_point] or list(pieces)
    if spans and all(piece.status == "match" for piece in spans) and not any(
        piece.status == "contradict" for piece in pieces
    ):
        return "TRUE"
    if spans and all(piece.status == "contradict" for piece in spans) and not any(
        piece.status == "match" for piece in pieces
    ):
        return "FALSE"
    return "UNKNOWN"


def sometime(pieces: Sequence[Piece]) -> Truth:
    if any(piece.status == "match" for piece in pieces):
        return "TRUE"
    spans = [piece for piece in pieces if not piece.is_point] or list(pieces)
    return "FALSE" if spans and all(piece.status == "contradict" for piece in spans) else "UNKNOWN"


type _Interval = StateInterval | RelationInterval


def _profile(
    intervals: Sequence[_Interval],
    start: float,
    end: float,
    classify,
) -> list[Piece]:
    def piece(lo: float, hi: float, interval: _Interval) -> Piece:
        status, target = classify(interval)
        return Piece(lo, hi, status, tuple(interval.support_observation_ids), target)

    if end - start <= EPSILON:
        touching = [
            piece(start, start, interval)
            for interval in intervals
            if interval.start_sec - EPSILON <= start <= interval.end_sec + EPSILON
        ]
        decisive = [item for item in touching if item.status != "unknown"]
        if decisive and len({item.status for item in decisive}) == 1:
            return [Piece(start, start, decisive[0].status,
                          tuple(sorted({o for item in decisive for o in item.support})), decisive[0].target)]
        return [Piece(start, start, "unknown")]
    pieces: list[Piece] = []
    cursor = start
    for interval in intervals:
        lo, hi = max(start, interval.start_sec), min(end, interval.end_sec)
        if interval.end_sec - interval.start_sec <= EPSILON:
            if start - EPSILON <= interval.start_sec <= end + EPSILON:
                pieces.append(piece(interval.start_sec, interval.start_sec, interval))
            continue
        if hi - lo <= EPSILON:
            continue
        if lo > cursor + EPSILON:
            pieces.append(Piece(cursor, lo, "unknown"))
        pieces.append(piece(lo, hi, interval))
        cursor = max(cursor, hi)
    if end > cursor + EPSILON:
        pieces.append(Piece(cursor, end, "unknown"))
    return sorted(pieces, key=lambda item: (item.start, item.end))


def state_profile(
    track: StateTrack,
    start: float,
    end: float,
    value: str,
    knowledge: str | None,
) -> list[Piece]:

    def classify(interval: StateInterval) -> tuple[PieceStatus, None]:
        if interval.knowledge == "unknown" or interval.value is None:
            return "unknown", None
        bounded = interval.knowledge == "bounded_by_observations"
        if interval.value == value and (bounded or knowledge is None):
            return "match", None
        if interval.value == OPPOSITE.get(value) and bounded:
            return "contradict", None
        return "unknown", None

    return _profile(track.intervals, start, end, classify)


def relation_profile(
    track: RelationTrack,
    start: float,
    end: float,
    target: str | None,
    knowledge: str | None,
) -> list[Piece]:

    def classify(interval: RelationInterval) -> tuple[PieceStatus, str | None]:
        if interval.knowledge == "unknown" or interval.target_status == "unknown":
            return "unknown", None
        bounded = interval.knowledge == "bounded_by_observations"
        if interval.target_status == "known_entity":
            if target is None or interval.target_entity_id == target:
                return ("match" if bounded or knowledge is None else "unknown"), interval.target_entity_id
            return ("contradict" if bounded else "unknown"), interval.target_entity_id
        return ("contradict" if bounded else "unknown"), None

    return _profile(track.intervals, start, end, classify)


@dataclass(slots=True)
class Evidence:

    events: set[str] = field(default_factory=set)
    state_tracks: set[str] = field(default_factory=set)
    relation_tracks: set[str] = field(default_factory=set)
    episodes: set[str] = field(default_factory=set)
    observations: set[str] = field(default_factory=set)
    frames: set[str] = field(default_factory=set)

    def add_event(self, event: Event) -> None:
        self.events.add(event.id)
        self.observations.update(event.support_observation_ids)
        self.frames.update(event.evidence_frame_ids)

    def add_pieces(self, track: StateTrack | RelationTrack, pieces: Iterable[Piece]) -> None:
        target = self.state_tracks if isinstance(track, StateTrack) else self.relation_tracks
        target.add(track.id)
        for piece in pieces:
            self.observations.update(piece.support)

    def merge(self, other: Evidence) -> None:
        self.events |= other.events
        self.state_tracks |= other.state_tracks
        self.relation_tracks |= other.relation_tracks
        self.episodes |= other.episodes
        self.observations |= other.observations
        self.frames |= other.frames


class STEGIndex:

    def __init__(self, graph: SparseTemporalEvidenceGraph) -> None:
        self.graph = graph
        self.duration = graph.video.duration_sec
        self.entities: dict[str, Entity] = {entity.id: entity for entity in graph.entities}
        self.events: dict[str, Event] = {event.id: event for event in graph.events}
        self.observations: dict[str, Observation] = {item.id: item for item in graph.observations}
        self.frame_times = {frame.id: frame.timestamp_sec for frame in graph.evidence_frames}
        self.episodes: dict[str, ProcedureEpisode] = {
            episode.id: episode for episode in graph.procedure_episodes
        }
        self.states: dict[tuple[str, str], list[StateTrack]] = defaultdict(list)
        self.relations: dict[str, list[RelationTrack]] = defaultdict(list)
        self.event_episodes: dict[str, set[str]] = defaultdict(set)
        self.flags: dict[str, list[QualityFlag]] = defaultdict(list)
        self.semantic = {
            (link.kind, link.record_id, link.observed, link.requirement)
            for link in graph.semantic_supports if link.supports is True
        }
        for track in graph.state_tracks:
            self.states[(track.entity_id, track.property)].append(track)
        for track in graph.relation_tracks:
            self.relations[track.relation].append(track)
        states = {track.id: track for track in graph.state_tracks}
        relations = {track.id: track for track in graph.relation_tracks}
        for kind, identifier, observed, requirement in self.semantic:
            if kind == "state":
                track = states[identifier]
                if observed != requirement:
                    self.states[(track.entity_id, requirement)].append(track)
            elif kind == "relation":
                track = relations[identifier]
                if observed != requirement:
                    self.relations[requirement].append(track)
        for episode in graph.procedure_episodes:
            for event_id in episode.event_ids:
                self.event_episodes[event_id].add(episode.id)
        for flag in graph.quality_flags:
            for reference in flag.reference_ids:
                self.flags[reference].append(flag)
        self._frame_order = sorted(self.frame_times.items(), key=lambda item: (item[1], item[0]))

    def bounds(self, event: Event) -> Bounds:
        return Bounds.of_event(event, self.duration)

    def supports(self, kind: str, identifier: str, observed: str, requirement: str) -> bool:
        return observed == requirement or (kind, identifier, observed, requirement) in self.semantic

    def action_matches(self, event: Event, action: str) -> bool:
        return self.supports("action", event.id, event.action, action)

    def episode_bounds(self, episode: ProcedureEpisode) -> Bounds:
        if episode.end_sec is not None:
            return Bounds.exact(episode.start_sec, episode.end_sec)
        members = [self.events[event_id].time.end_sec for event_id in episode.event_ids]
        earliest = max([episode.start_sec, *members])
        return Bounds(episode.start_sec, earliest, episode.start_sec, episode.start_sec, earliest, self.duration)

    def episodes_of(self, kind: str) -> list[ProcedureEpisode]:
        return sorted(
            (episode for episode in self.episodes.values()
             if self.supports("episode", episode.id, episode.kind, kind)),
            key=lambda episode: (episode.start_sec, episode.id),
        )

    def members(self, episode: ProcedureEpisode) -> list[Event]:
        events = [self.events[event_id] for event_id in episode.event_ids]
        return sorted(events, key=lambda event: (event.time.start_sec, event.id))

    def entities_of(self, kind: str, subtype: str) -> list[str]:
        return sorted(
            entity.id
            for entity in self.entities.values()
            if entity.kind == kind and self.supports("entity", entity.id, entity.subtype, subtype)
        )

    def state_tracks(self, entity_id: str, prop: str) -> list[StateTrack]:
        return self.states.get((entity_id, prop), [])

    def relation_tracks(self, relation: str, subject_id: str | None = None) -> list[RelationTrack]:
        return [
            track
            for track in self.relations.get(relation, [])
            if subject_id is None or track.subject_id == subject_id
        ]

    def role_holders(self, episode: ProcedureEpisode, role: str) -> set[str]:
        return {
            participant.entity_id
            for event in self.members(episode)
            for participant in event.participants
            if self.supports("role", event.id, participant.role, role)
        }

    def episode_role(
        self, episode: ProcedureEpisode, role: str
    ) -> tuple[str | None, RoleProblem | None]:
        holders = self.role_holders(episode, role)
        if not holders:
            return None, "missing_binding"
        if len(holders) > 1:
            return None, "ambiguous_role"
        (entity_id,) = holders
        if self.entities[entity_id].identity_status == "ambiguous":
            return None, "ambiguous_role"
        return entity_id, None

    def proven_absent(
        self,
        action: str,
        subjects: Iterable[str],
        start: float,
        end: float,
        *,
        verified: bool = False,
    ) -> tuple[bool, Evidence]:
        evidence = Evidence()
        for subject in subjects:
            tracks = self.state_tracks(subject, action)
            if len(tracks) != 1:
                continue
            pieces = state_profile(tracks[0], start, end, "false", "bounded_by_observations")
            if throughout(pieces) != "TRUE":
                continue
            if verified and not self._verified(pieces):
                continue
            evidence.add_pieces(tracks[0], pieces)
            return True, evidence
        return False, evidence

    def _verified(self, pieces: Iterable[Piece]) -> bool:
        for piece in pieces:
            if not piece.support:
                return False
            for observation_id in piece.support:
                observation = self.observations[observation_id]
                if observation.reliability != "high" or observation.source_stage not in VERIFIED_STAGES:
                    return False
        return True

    def frames_for(self, evidence: Evidence) -> dict[str, float]:
        frames = set(evidence.frames)
        for observation_id in evidence.observations:
            frames.update(self.observations[observation_id].evidence_frame_ids)
        return {frame: self.frame_times[frame] for frame in frames}

    def nearest_frames(self, time: float, limit: int) -> dict[str, float]:
        times = [moment for _, moment in self._frame_order]
        index = bisect_right(times, time)
        nearby = self._frame_order[max(0, index - limit) : index + limit]
        nearby.sort(key=lambda item: (abs(item[1] - time), item[1]))
        return dict(nearby[:limit])

    def flags_for(self, references: Iterable[str]) -> list[QualityFlag]:
        found: dict[str, QualityFlag] = {}
        for reference in references:
            for flag in self.flags.get(reference, []):
                found[flag.id] = flag
        return [found[key] for key in sorted(found)]

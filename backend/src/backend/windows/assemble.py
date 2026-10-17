import re
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from backend.reconstruction.decode import Observation
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, decode_tracks
from backend.reconstruction.probes import PROBES
from backend.reconstruction.video import DecodedVideo
from backend.steg import Event, Participant, SparseTemporalEvidenceGraph, TimeSpan
from backend.steg import Observation as GraphObservation
from backend.windows.models import Window
from backend.windows.vocabulary import ACTIONS, STATES

CLAIMED, DENIED, UNREPORTED = 0.95, 0.05, 0.2
TOLERANCE = 0.25
MERGE_GAP = 1.0
OPEN_PREFIX = "w_e"
IMPLIES = {"cashier_seated": "cashier_at_station", "cashier_at_station": "room_occupied",
           "customer_present": "room_occupied"}

type Interval = tuple[float, float]


@dataclass(slots=True)
class Claims:
    start: float
    end: float
    states: dict[str, list[Interval]] = field(default_factory=lambda: defaultdict(list))
    implied: dict[str, list[Interval]] = field(default_factory=lambda: defaultdict(list))
    denied: set[str] = field(default_factory=set)
    actions: dict[str, list[Interval]] = field(default_factory=lambda: defaultdict(list))
    open_actions: list[tuple[str, float, float, str, str]] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def canonical(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _place(window: Window, start: float, end: float) -> Interval | None:
    start, end = sorted((start, end))
    if start < window.start_sec - 1 and end <= window.end_sec - window.start_sec + 1:
        start, end = start + window.start_sec, end + window.start_sec
    start, end = max(window.start_sec, start), min(window.end_sec, end)
    return (start, end) if start <= end else None


def claims(window: Window) -> Claims:
    result = Claims(window.start_sec, window.end_sec)
    graph = window.graph
    spans = [(span.name, span) for span in graph.true_states] + [(action.name, action) for action in graph.actions]
    for raw, span in spans:
        name, placed = canonical(raw), _place(window, span.start_sec, span.end_sec)
        if placed is None:
            result.dropped.append(raw)
        elif name in STATES:
            result.states[name].append(placed)
        elif name in ACTIONS:
            result.actions[name].append(placed)
        elif name and hasattr(span, "actor"):
            result.open_actions.append((name, *placed, span.actor, span.recipient))
        else:
            result.dropped.append(raw)
    result.denied = {name for name in map(canonical, graph.false_states) if name in STATES} - set(result.states)
    for cause in IMPLIES:
        consequence, intervals = IMPLIES[cause], result.states.get(cause, []) + result.implied.get(cause, [])
        if intervals and consequence not in result.states and consequence not in result.denied:
            result.implied[consequence].extend(intervals)
    return result


def _covered(intervals: list[Interval], moment: float) -> bool:
    return any(start - TOLERANCE <= moment <= end + TOLERANCE for start, end in intervals)


def probability(observed: list[Claims], key: str, moment: float) -> float:
    votes = []
    for claim in observed:
        if not claim.start - 1e-6 <= moment <= claim.end + 1e-6:
            continue
        if key in ACTIONS:
            votes.append(CLAIMED if _covered(claim.actions.get(key, []), moment) else UNREPORTED)
        elif key in claim.states:
            votes.append(CLAIMED if _covered(claim.states[key], moment) else DENIED)
        elif key in claim.denied:
            votes.append(DENIED)
        elif _covered(claim.implied.get(key, []), moment):
            votes.append(CLAIMED)
    return float(np.mean(votes)) if votes else 0.5


def reconstruct(video: DecodedVideo, observed: list[Claims], observer_model: str) -> Reconstruction:
    tracks = {probe.key: AttributeTrack(probe, [Observation(float(moment), probability(observed, probe.key, float(moment)))
                                                for moment in video.times]) for probe in PROBES}
    decode_tracks(video, tracks)
    return Reconstruction(video, tracks, observer_model)


def _merge(spans: list[Interval]) -> list[tuple[float, float, list[Interval]]]:
    merged: list[tuple[float, float, list[Interval]]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1] + MERGE_GAP:
            first, last, members = merged[-1]
            merged[-1] = (first, max(last, end), members + [(start, end)])
        else:
            merged.append((start, end, [(start, end)]))
    return merged


def add_open_actions(graph: SparseTemporalEvidenceGraph, observed: list[Claims],
                     video: DecodedVideo) -> SparseTemporalEvidenceGraph:
    frame_ids = [f"f_{index}" for index in video.frame_indices]
    duration = graph.video.duration_sec
    customers = [entity.id for entity in graph.entities if entity.role == "customer"]
    episodes = [episode.model_copy(deep=True) for episode in graph.procedure_episodes]
    visits = list(zip(customers, episodes, strict=True))

    def frame(moment: float) -> str:
        return frame_ids[int(np.argmin(np.abs(video.times - moment)))]

    def customer_at(moment: float) -> str | None:
        return next((customer for customer, episode in visits if episode.start_sec <= moment
                     <= (duration if episode.end_sec is None else episode.end_sec)), None)

    groups = defaultdict(list)
    for claim in observed:
        for name, start, end, actor, recipient in claim.open_actions:
            groups[(name, actor, recipient)].append((start, end))
    observations, added = list(graph.observations), []
    for (name, actor, recipient), spans in sorted(groups.items()):
        for start, end, members in _merge(spans):
            people = {"cashier": "person_1", "customer": customer_at((start + end) / 2)}
            participants = [Participant(role=role, entity_id=people[role])
                            for role in dict.fromkeys((actor, recipient)) if people.get(role)]
            participants = participants or [Participant(role="location", entity_id="room_1")]
            support = []
            for low, high in members:
                moment = (low + high) / 2
                observations.append(GraphObservation(
                    id=f"w_o{len(observations) + 1}", timestamp_sec=moment, subject_id=participants[0].entity_id,
                    predicate=name, value="true", visibility="unknown", evidence_frame_ids=[frame(moment)],
                    source_stage="coarse_vlm", reliability="medium", notes="Open-vocabulary action from one window",
                ))
                support.append(observations[-1].id)
            added.append(Event(
                id=f"{OPEN_PREFIX}{len(added) + 1}", action=name,
                time=TimeSpan(start_sec=start, end_sec=end, start_uncertainty_sec=0.5, end_uncertainty_sec=0.5),
                participants=participants, support_observation_ids=support,
                evidence_frame_ids=list(dict.fromkeys(frame(moment) for moment in (start, (start + end) / 2, end))),
                inference_status="inferred_from_observations", verification_status="first_pass",
                note=f"Reported by {len(members)} window(s); actor {actor}, recipient {recipient}",
            ))
    for customer, episode in visits:
        end = duration if episode.end_sec is None else episode.end_sec
        for event in added:
            others = {p.entity_id for p in event.participants if p.role == "customer"} - {customer}
            if event.time.end_sec >= episode.start_sec and event.time.start_sec <= end and not others:
                episode.event_ids.append(event.id)
    events = sorted(graph.events + added, key=lambda event: (event.time.start_sec, event.id))
    return graph.model_copy(update={"events": events, "observations": observations, "procedure_episodes": episodes})


def timeline(reconstruction: Reconstruction, observed: list[Claims], window_sec: float, stride_sec: float,
             pipeline: str) -> SparseTemporalEvidenceGraph:
    graph = build_timeline(reconstruction)
    processing = graph.processing.model_copy(update={
        "window_sec": window_sec, "stride_sec": stride_sec, "pipeline_version": pipeline,
    })
    observations = [observation.model_copy(update={
        "notes": observation.notes.replace("Uncalibrated yes/no score", "Window vote share"),
    }) for observation in graph.observations]
    graph = graph.model_copy(update={"processing": processing, "observations": observations})
    graph = add_open_actions(graph, observed, reconstruction.video)
    return SparseTemporalEvidenceGraph.model_validate(graph.model_dump(mode="json"))

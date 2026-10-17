from collections import defaultdict

from backend.followup.models import EvidenceQuestion, VisualAnswer
from backend.followup.observer import ReplayFrame
from backend.steg import (
    Event, Observation, RelationInterval, RelationTrack, ScanWindow,
    SparseTemporalEvidenceGraph, StateInterval, StateTrack, TimeSpan,
)


def _overlay(existing, new):
    kept = []
    for interval in existing:
        if interval.end_sec < new.start_sec or interval.start_sec > new.end_sec:
            kept.append(interval)
            continue
        if interval.start_sec < new.start_sec:
            kept.append(interval.model_copy(update={"end_sec": new.start_sec}))
        if interval.end_sec > new.end_sec:
            kept.append(interval.model_copy(update={"start_sec": new.end_sec}))
    return sorted(kept + [new], key=lambda interval: (interval.start_sec, interval.end_sec))


def merge_answer(graph: SparseTemporalEvidenceGraph, question: EvidenceQuestion,
                 answer: VisualAnswer, frames: list[ReplayFrame]) -> SparseTemporalEvidenceGraph:
    result = graph.model_copy(deep=True)
    supplied = {frame.evidence.id: frame.evidence for frame in frames}
    entity_ids = {entity.id for entity in result.entities}
    changed_records = set()
    referenced = {fact.subject_id for fact in answer.facts} | {
        fact.object_entity_id for fact in answer.facts if fact.object_entity_id is not None
    } | {participant.entity_id for action in answer.actions for participant in action.participants}
    for entity in answer.entities:
        if entity.id not in entity_ids and entity.id in referenced:
            result.entities.append(entity.model_copy(update={"identity_status": "provisional"}))
            entity_ids.add(entity.id)
    observations = []
    groups = defaultdict(list)

    def observation(frame_id, subject, predicate, value, target, visibility, reliability):
        frame = supplied[frame_id]
        if subject not in entity_ids or (target is not None and target not in entity_ids):
            raise ValueError("Visual evidence references an ungrounded entity")
        fields = {"object_entity_id": target} if target is not None else {"value": value or "unknown"}
        record = Observation(
            id=f"replay_o_{len(result.observations) + len(observations) + 1}",
            timestamp_sec=frame.timestamp_sec, subject_id=subject, predicate=predicate,
            visibility=visibility, evidence_frame_ids=[frame.id], source_stage="replay_vlm",
            reliability=reliability, notes=f"Focused check {question.id}", **fields,
        )
        observations.append(record)
        return record

    for fact in answer.facts:
        record = observation(fact.frame_id, fact.subject_id, fact.predicate, fact.value,
                             fact.object_entity_id, fact.visibility, fact.reliability)
        visible = fact.visibility in {"clear", "partial"} and fact.reliability != "low"
        value = fact.value if visible else None
        relation = fact.kind == "relation" or fact.object_entity_id is not None
        groups[(fact.subject_id, fact.predicate, value, fact.object_entity_id, visible, relation)].append(record)
    positions = {frame.evidence.id: index for index, frame in enumerate(frames)}
    for (subject, predicate, value, target, visible, relation), records in groups.items():
        records.sort(key=lambda record: record.timestamp_sec)
        chunks = []
        for record in records:
            previous = chunks[-1][-1] if chunks else None
            contiguous = previous is not None and record.timestamp_sec - previous.timestamp_sec <= 1.0
            contiguous = contiguous and positions[record.evidence_frame_ids[0]] == positions[previous.evidence_frame_ids[0]] + 1
            if question.matcher.kind == "event" and value != "true":
                contiguous = False
            if contiguous:
                chunks[-1].append(record)
            else:
                chunks.append([record])
        collection = result.relation_tracks if relation else result.state_tracks
        track = next((track for track in collection
                      if (track.subject_id if relation else track.entity_id) == subject
                      and (track.relation if relation else track.property) == predicate), None)
        for chunk in chunks:
            known = visible and (target is not None or value in {"false", "none"}) if relation else value is not None
            fields = dict(start_sec=chunk[0].timestamp_sec, end_sec=chunk[-1].timestamp_sec,
                          knowledge="bounded_by_observations" if known else "unknown",
                          support_observation_ids=[record.id for record in chunk], note=f"Focused check {question.id}")
            status = "known_entity" if target is not None else "known_none"
            interval = (RelationInterval(**fields, target_status=status if known else "unknown",
                                         target_entity_id=target if known else None)
                        if relation else StateInterval(**fields, value=value))
            if track is None:
                identifier = f"replay_t_{question.id}_{len(result.state_tracks) + len(result.relation_tracks)}"
                track = (RelationTrack(id=identifier, subject_id=subject, relation=predicate, intervals=[interval])
                         if relation else StateTrack(id=identifier, entity_id=subject, property=predicate, intervals=[interval]))
                collection.append(track)
            else:
                track.intervals = _overlay(track.intervals, interval)
            changed_records.add(track.id)
    for action in answer.actions:
        if not action.participants or any(participant.entity_id not in entity_ids for participant in action.participants):
            raise ValueError("Observed action has no grounded participants")
        first, last = supplied[action.first_frame_id], supplied[action.last_frame_id]
        if first.timestamp_sec > last.timestamp_sec:
            raise ValueError("Observed action cites frames in reverse order")
        evidence = [supplied[identifier] for identifier in action.evidence_frame_ids]
        if not evidence:
            raise ValueError("Observed action must cite its visible evidence")
        support = [observation(frame.id, action.participants[0].entity_id, action.action, "true", None,
                               "unknown", action.reliability).id for frame in evidence]
        actors = {participant.entity_id for participant in action.participants}
        existing = next((event for event in result.events if event.action == action.action
                         and (event.id in question.window.anchor_ids or
                              event.time.start_sec <= last.timestamp_sec and event.time.end_sec >= first.timestamp_sec)
                         and actors & {participant.entity_id for participant in event.participants}), None)
        event = Event(
            id=existing.id if existing else f"replay_e_{len(result.events) + 1}", action=action.action,
            time=TimeSpan(start_sec=first.timestamp_sec, end_sec=last.timestamp_sec),
            participants=action.participants, support_observation_ids=support,
            evidence_frame_ids=[frame.id for frame in evidence],
            inference_status="directly_observed" if action.reliability == "high" else "hypothesis",
            verification_status="replayed", note=action.description,
        )
        if existing:
            result.events[result.events.index(existing)] = event
        else:
            result.events.append(event)
        changed_records.add(event.id)
        episode = next((episode for episode in result.procedure_episodes if episode.id == question.episode_id), None)
        if episode is not None and event.id not in episode.event_ids:
            episode.event_ids.append(event.id)
    result.observations.extend(observations)
    existing_frames = {frame.id for frame in result.evidence_frames}
    result.evidence_frames.extend(frame for identifier, frame in supplied.items() if identifier not in existing_frames)
    result.observation_coverage.scan_windows.append(ScanWindow(
        id=f"replay_{question.id}", start_sec=min(frame.timestamp_sec for frame in supplied.values()),
        end_sec=max(frame.timestamp_sec for frame in supplied.values()), status="processed",
        sampled_frame_ids=list(supplied),
    ))
    result.events.sort(key=lambda event: (event.time.start_sec, event.id))
    result.semantic_supports = [link for link in result.semantic_supports if link.record_id not in changed_records]
    return result

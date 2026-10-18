"""Observe cash provenance across frames, without dataset labels or video names."""
import logging
from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from backend.followup.models import StructuredModel
from backend.reconstruction.video import DecodedVideo
from backend.steg import Event, Observation, Participant, SparseTemporalEvidenceGraph, TimeSpan

logger = logging.getLogger(__name__)


class CashAction(BaseModel):
    action: Literal["rejected_banknotes_recombined", "different_customer_cash_mixed"]
    first_frame_id: str
    last_frame_id: str
    evidence_frame_ids: list[str] = Field(min_length=2)
    origins_visible: bool
    status: Literal["observed", "uncertain"]
    explanation: str


class CashActions(BaseModel):
    actions: list[CashAction] = Field(default_factory=list)


@dataclass
class TemporalResult:
    graph: SparseTemporalEvidenceGraph
    calls: int = 0
    errors: list[str] = field(default_factory=list)


def observe_cash_provenance(
    graph: SparseTemporalEvidenceGraph, video: DecodedVideo, model: StructuredModel,
    image_tokens: int = 512, window_sec: float = 12.0, stride_sec: float = 6.0,
) -> TemporalResult:
    if window_sec <= 0 or stride_sec <= 0 or image_tokens <= 0:
        raise ValueError("Window, stride and image token budget must be positive")
    result = TemporalResult(graph.model_copy(deep=True))
    receipts = sorted((event for event in graph.events if event.action == "cash_received"),
                      key=lambda event: event.time.start_sec)
    frame_lookup = {frame.id: frame for frame in graph.evidence_frames}
    start = 0.0
    while start < video.duration:
        end = min(video.duration, start + window_sec)
        current = np.flatnonzero((video.times >= start) & (video.times <= end))
        if not len(current):
            break
        chosen = set(current[np.linspace(0, len(current) - 1, min(6, len(current))).astype(int)].tolist())
        # Up to two earlier receipts supply origin evidence across customer visits.
        for receipt in [event for event in receipts if event.time.start_sec < start][-2:]:
            chosen.add(int(np.argmin(np.abs(video.times - receipt.time.start_sec))))
        selected = sorted(chosen)
        identifiers = [f"f_{video.frame_indices[index]}" for index in selected]
        frames = [frame_lookup[identifier] for identifier in identifiers]
        prompt = (
            "Inspect this chronological sequence from a bank cash desk. Only report these two actions "
            f"when they occur inside {start:.2f}-{end:.2f} seconds:\n"
            "1. rejected_banknotes_recombined: notes visibly rejected by the counting machine are "
            "put back together with accepted notes without a visible inspection. If an inspection "
            "is seen, do not report this action. Machine rejection does not prove counterfeit money.\n"
            "2. different_customer_cash_mixed: notes visibly originating from different customers or "
            "operations are combined. Combining piles belonging to the same customer is not this action.\n"
            "Earlier receipt frames may be included only to establish origins. Do not assume that two "
            "piles have different owners or that ordinary machine use is a rejection. Use observed "
            "only when the relevant origins, handling and recombination are visible. If rejection, "
            "origins or inspection are unclear, use uncertain with origins_visible=false. Empty actions "
            "is correct when neither action is supported. Never infer banking-system recording, legal "
            "compliance, or counterfeit authenticity from these frames. Do not output verdicts.\n"
            "Reference only supplied frame IDs. Action start/end must be within the current window; "
            "evidence may also reference the earlier receipt frames. Frames in image order:\n"
            + "\n".join(f"{frame.id}: {frame.timestamp_sec:.2f}s" for frame in frames)
        )
        result.calls += 1
        call_started = perf_counter()
        logger.info(
            "Video %s: temporal scan %s, %.2f-%.2fs (%s frames) started",
            video.path.stem, result.calls, start, end, len(frames),
        )
        try:
            answer = model.structured(prompt, CashActions,
                                      images=[video.frame_at(frame.timestamp_sec) for frame in frames],
                                      image_tokens=image_tokens, max_new_tokens=1024)
            for action in answer.actions:
                _merge_action(result.graph, action, set(identifiers), start, end)
        except Exception as error:
            detail = f"{start:.2f}-{end:.2f}s: {error}"
            result.errors.append(detail)
            logger.warning("Cash provenance scan failed: %s", detail)
        logger.info(
            "Video %s: temporal scan %s finished in %.1fs",
            video.path.stem, result.calls, perf_counter() - call_started,
        )
        if end == video.duration:
            break
        start += stride_sec
    result.graph.events.sort(key=lambda event: (event.time.start_sec, event.id))
    return result


def _merge_action(graph: SparseTemporalEvidenceGraph, action: CashAction,
                  allowed: set[str], window_start: float, window_end: float) -> None:
    evidence = list(dict.fromkeys(action.evidence_frame_ids))
    referenced = {action.first_frame_id, action.last_frame_id, *evidence}
    if (not referenced <= allowed or len(evidence) < 2
            or not {action.first_frame_id, action.last_frame_id} <= set(evidence)):
        raise ValueError("Cash action references unknown frames or lacks two distinct evidence frames")
    frames = {frame.id: frame for frame in graph.evidence_frames}
    start, end = frames[action.first_frame_id].timestamp_sec, frames[action.last_frame_id].timestamp_sec
    if not window_start <= start <= end <= window_end:
        raise ValueError("Cash action falls outside its observation window")
    confirmed = action.status == "observed" and action.origins_visible
    # Keep uncertain observations for review, but never upgrade them through overlap.
    status = "directly_observed" if confirmed else "hypothesis"
    existing = next((event for event in graph.events if event.action == action.action
                     and event.inference_status == status
                     and event.time.start_sec <= end and start <= event.time.end_sec), None)
    observations = []
    for identifier in evidence:
        observation_id = f"cash_temporal_o{len(graph.observations) + 1}"
        graph.observations.append(Observation(
            id=observation_id, timestamp_sec=frames[identifier].timestamp_sec,
            subject_id="person_1", predicate=action.action, value="true" if confirmed else None,
            visibility="clear" if confirmed else "unknown", evidence_frame_ids=[identifier],
            source_stage="replay_vlm", reliability="medium" if confirmed else "low",
            notes=action.explanation,
        ))
        observations.append(observation_id)
    if existing:
        existing.time.start_sec = min(existing.time.start_sec, start)
        existing.time.end_sec = max(existing.time.end_sec, end)
        existing.evidence_frame_ids = list(dict.fromkeys(existing.evidence_frame_ids + evidence))
        existing.support_observation_ids.extend(observations)
    else:
        graph.events.append(Event(
            id=f"cash_temporal_e{len(graph.events) + 1}", action=action.action,
            time=TimeSpan(start_sec=start, end_sec=end),
            participants=[Participant(role="cashier", entity_id="person_1")],
            support_observation_ids=observations, evidence_frame_ids=evidence,
            inference_status=status, verification_status="replayed", note=action.explanation,
        ))

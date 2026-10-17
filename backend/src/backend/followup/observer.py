import json
from dataclasses import dataclass

import cv2
import numpy as np

from backend.followup.models import EvidenceQuestion, StructuredModel, VisualAnswer
from backend.reconstruction.video import DecodedVideo
from backend.steg import EvidenceFrame, SparseTemporalEvidenceGraph


@dataclass(slots=True)
class ReplayFrame:
    evidence: EvidenceFrame
    image: np.ndarray
    jpeg: bytes


def sample_window(video: DecodedVideo, start: float, end: float, limit: int = 8) -> list[ReplayFrame]:
    count = min(limit, max(1, int((end - start) * 2) + 1))
    capture = cv2.VideoCapture(str(video.path))
    frames = {}
    try:
        for moment in np.linspace(start, min(end, video.duration - 1 / video.native_fps), count):
            capture.set(cv2.CAP_PROP_POS_MSEC, float(moment) * 1000)
            ok, image = capture.read()
            if not ok:
                continue
            index = int(capture.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if timestamp == 0 and index > 0:
                timestamp = index / video.native_fps
            _, encoded = cv2.imencode(".jpg", image)
            evidence = EvidenceFrame(
                id=f"f_{index}", timestamp_sec=timestamp, source_ref=video.path.name,
                original_frame_index=index,
            )
            frames[evidence.id] = ReplayFrame(evidence, image, encoded.tobytes())
    finally:
        capture.release()
    return sorted(frames.values(), key=lambda frame: frame.evidence.timestamp_sec)


def timeline_context(graph: SparseTemporalEvidenceGraph, question: EvidenceQuestion) -> dict:
    start, end = question.window.start_sec, question.window.end_sec
    events = [event.model_dump(mode="json") for event in graph.events
              if event.time.start_sec <= end and event.time.end_sec >= start]
    states = [{"id": track.id, "entity_id": track.entity_id, "property": track.property,
               "intervals": [interval.model_dump(mode="json") for interval in track.intervals
                             if interval.start_sec <= end and interval.end_sec >= start]}
              for track in graph.state_tracks]
    relations = [{"id": track.id, "subject_id": track.subject_id, "relation": track.relation,
                  "intervals": [interval.model_dump(mode="json") for interval in track.intervals
                                if interval.start_sec <= end and interval.end_sec >= start]}
                 for track in graph.relation_tracks]
    return {"entities": [entity.model_dump(mode="json") for entity in graph.entities],
            "events": events, "state_tracks": [track for track in states if track["intervals"]],
            "relation_tracks": [track for track in relations if track["intervals"]]}


class FocusedObserver:
    def __init__(self, model: StructuredModel, video: DecodedVideo, max_frames: int = 8) -> None:
        self.model, self.video, self.max_frames = model, video, max_frames

    def answer(self, question: EvidenceQuestion, graph: SparseTemporalEvidenceGraph):
        frames = sample_window(self.video, question.window.start_sec, question.window.end_sec, self.max_frames)
        if not frames:
            raise ValueError("No frames available in the requested time window")
        prompt = (
            "Inspect these ordered video frames to resolve the evidence request. Match the visible "
            "people and objects to the supplied graph entity IDs; do not guess ambiguous identities. "
            "For a newly visible entity, provide a new provisional entity. The graph is prior context, "
            "not proof: report only what the supplied frames show. Describe actions in their observed "
            "terms and assign participant roles. Cite only supplied frame IDs, including each action's "
            "first and last frame. Use facts for visible states or relations on individual frames. "
            "Set kind=relation for subject/object relations, with object_entity_id for a visible target "
            "or value=false when the relation is explicitly absent. Use true/false for binary facts; "
            "unseen and ambiguous details have value=null and unknown "
            "visibility. A missed action between samples does not prove it never happened. "
            "Return uncertain or not_visible when necessary. Do not output rule verdicts.\n"
            + json.dumps({"request": question.model_dump(mode="json"),
                          "frames_in_image_order": [frame.evidence.model_dump(mode="json") for frame in frames],
                          "timeline": timeline_context(graph, question)}, ensure_ascii=False)
        )
        answer = self.model.structured(prompt, VisualAnswer, images=[frame.image for frame in frames], max_new_tokens=2048)
        return answer, frames

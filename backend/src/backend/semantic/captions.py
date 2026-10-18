"""Sliding-window prose -> semantic questions -> existing timeline and rule engine."""
from dataclasses import dataclass

import numpy as np

from backend.reconstruction.decode import Observation, Segment
from backend.reconstruction.graph import CLAIMS, build_timeline
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, decode_tracks
from backend.reconstruction.probes import PERCEPTION_PROBES, SCENE_CONTEXT
from backend.reconstruction.video import DecodedVideo


@dataclass(frozen=True)
class CaptionConfig:
    window_seconds: float = 8
    stride_seconds: float = 4
    frames: int = 6
    tokens: int = 96
    image_tokens: int = 256
    threshold: float = 0.75

    def __post_init__(self):
        if not 0 < self.stride_seconds <= self.window_seconds:
            raise ValueError("Require 0 < stride <= window for full coverage")
        if self.frames < 2 or self.tokens < 1 or not 0.5 < self.threshold < 1:
            raise ValueError("Require >=2 frames, positive tokens, and 0.5 < threshold < 1")


def windows(duration: float, config: CaptionConfig):
    if duration <= 0:
        raise ValueError("Video duration must be positive")
    start = 0.0
    while True:
        end = min(duration, start + config.window_seconds)
        yield start, end
        if end >= duration:
            break
        start += config.stride_seconds


def describe_windows(model, video: DecodedVideo, config: CaptionConfig, progress=None):
    result = []
    for number, (start, end) in enumerate(windows(video.duration, config), 1):
        available = np.flatnonzero((video.times >= start) & (video.times < end))
        if not len(available):
            raise ValueError(f"No sampled frames in window {start}-{end}")
        chosen = available[np.unique(np.linspace(0, len(available) - 1, min(config.frames, len(available))).round().astype(int))]
        times = [float(video.times[i]) for i in chosen]
        prompt = (
            SCENE_CONTEXT + " These frames are in chronological order. Describe only what is visibly "
            "happening in one or two short sentences. Mention the cashier's actions, people entering or "
            "leaving, exchanges, money and objects on the desk, the safe, door and computer when visible. "
            "Preserve who gives and who receives. Say unclear for ambiguous details. Do not infer intention, "
            "identity checks, unseen steps or legal violations. Use ordinary prose, without JSON, lists, "
            "invented IDs or invented timestamps.\nActual frame times: " + ", ".join(f"{t:.2f}s" for t in times)
        )
        if progress:
            progress(f"caption {number}: {start:.1f}-{end:.1f}s")
        caption = model.text(prompt, [video.frame_at(t) for t in times], config.image_tokens, config.tokens)
        scores = model.entail(caption, [probe.question for probe in PERCEPTION_PROBES])
        if len(scores) != len(PERCEPTION_PROBES):
            raise ValueError("Semantic matcher returned the wrong number of answers")
        result.append({"start": start, "end": end, "frame_times": times, "text": caption,
                       "scores": dict(zip([p.key for p in PERCEPTION_PROBES], scores, strict=True))})
    return result


def caption_probabilities(video, captions, threshold):
    result = {}
    for probe in PERCEPTION_PROBES:
        logits = [[] for _ in video.times]
        for caption in captions:
            yes, no, unknown = caption["scores"][probe.key]
            if max(yes, no) < threshold or unknown >= max(yes, no):
                continue
            probability = float(np.clip(0.5 + (yes - no) / 2, 1e-4, 1 - 1e-4))
            for index in np.flatnonzero((video.times >= caption["start"]) & (video.times < caption["end"])):
                logits[index].append(float(np.log(probability / (1 - probability))))
        # Overlap is averaged rather than counted as repeated independent evidence.
        result[probe.key] = np.array([1 / (1 + np.exp(-np.mean(values))) if values else 0.5 for values in logits])
    return result


def preserve_unknowns(video, track):
    """Keep an unmentioned fact unknown even if HMM smoothing prefers its neighbours."""
    unknown = np.array([abs(o.probability - 0.5) < 1e-8 for o in track.observations])
    states = np.zeros(len(video.times), dtype=bool)
    for segment in track.segments:
        states[segment.first:segment.last + 1] = segment.value
    posterior = np.asarray(track.posterior)
    posterior[unknown] = 0.5
    first, output = 0, []
    for last in range(1, len(states) + 1):
        if last < len(states) and (states[last], unknown[last]) == (states[first], unknown[first]):
            continue
        confidence = 0.5 if unknown[first] else float(np.mean(posterior[first:last] if states[first] else 1 - posterior[first:last]))
        start = float((video.times[first - 1] + video.times[first]) / 2) if first else 0.0
        end = float((video.times[last - 1] + video.times[last]) / 2) if last < len(states) else video.duration
        output.append(Segment(first, last - 1, bool(states[first]), confidence, start, end))
        first = last
    track.segments, track.posterior = output, posterior.tolist()


def reconstruct_captions(video, captions, config: CaptionConfig, model_name, baseline=None):
    values = caption_probabilities(video, captions, config.threshold)
    tracks = {}
    for probe in PERCEPTION_PROBES:
        probabilities = values[probe.key]
        if baseline is not None and probe.key in baseline.tracks:
            base = baseline.tracks[probe.key]
            observed = np.interp(video.times, [o.time for o in base.observations], [o.probability for o in base.observations])
            probabilities = np.where(abs(probabilities - 0.5) < 1e-8, observed, probabilities)
        tracks[probe.key] = AttributeTrack(probe, [Observation(float(t), float(p)) for t, p in zip(video.times, probabilities, strict=True)])
    decode_tracks(video, tracks)
    for track in tracks.values():
        preserve_unknowns(video, track)
    return Reconstruction(video, tracks, model_name)


def caption_graph(video, captions, config: CaptionConfig, model_name, baseline=None):
    graph = build_timeline(reconstruct_captions(video, captions, config, model_name, baseline))
    graph.processing = graph.processing.model_copy(update={"window_sec": config.window_seconds,
        "stride_sec": config.stride_seconds, "pipeline_version": "plain-caption-semantic-v1"})
    keys = {(subject, prop): key for key, (subject, prop, _, _) in CLAIMS.items()}
    for observation in graph.observations:
        key = keys.get((observation.subject_id, observation.predicate))
        relevant = [c for c in captions if c["start"] <= observation.timestamp_sec < c["end"]]
        strong = [c for c in relevant if max(c["scores"][key][:2]) >= config.threshold] if key else []
        if baseline is not None and not strong:
            continue
        observation.notes = "Inferred from prose over a sliding window; not localized to a single frame."
        if not strong:
            observation.value = None
            observation.reliability = "low"
        frame_ids = sorted({f"f_{video.frame_indices[int(np.argmin(abs(video.times - t)))]}"
                            for c in (strong or relevant) for t in c.get("frame_times", [])})
        if frame_ids:
            observation.evidence_frame_ids = frame_ids
    for event in graph.events:
        event.note = (event.note or "") + " Evidence may come from window prose; boundaries are coarse."
    return graph

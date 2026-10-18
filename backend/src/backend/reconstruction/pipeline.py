import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from time import perf_counter

import numpy as np

from backend.reconstruction.decode import Observation, Segment, decode_binary, segments, switch_probabilities
from backend.reconstruction.probes import PROBES, SCENE_CONTEXT, Probe
from backend.reconstruction.video import DecodedVideo, decode
from backend.reconstruction.vlm import QuestionVLM

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AttributeTrack:
    probe: Probe
    observations: list[Observation] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    posterior: list[float] = field(default_factory=list)


@dataclass(slots=True)
class Reconstruction:
    video: DecodedVideo
    tracks: dict[str, AttributeTrack]
    observer_model: str


class Reconstructor:
    def __init__(self, vlm: QuestionVLM, sample_fps: float = 1.0, image_tokens: int = 256) -> None:
        self.vlm = vlm
        self.sample_fps = sample_fps
        self.image_tokens = image_tokens

    def run(self, path: Path) -> Reconstruction:
        started = perf_counter()
        logger.info("Video %s: decoding at %s sample FPS", path.stem, self.sample_fps)
        video = decode(path, self.sample_fps)
        tracks = {probe.key: AttributeTrack(probe) for probe in PROBES}
        questions = [probe.question for probe in PROBES]
        logger.info(
            "Video %s: %.1fs duration, %s sampled frames, %s questions per frame; probing started",
            path.stem, video.duration, len(video.times), len(questions),
        )
        for index, moment in enumerate(video.times, start=1):
            frame_started = perf_counter()
            answers = self.vlm.probe(video.frame_at(moment), questions, SCENE_CONTEXT, self.image_tokens)
            for probe, probability in zip(PROBES, answers, strict=True):
                tracks[probe.key].observations.append(Observation(float(moment), probability))
            logger.info(
                "Video %s: frame %s/%s at %.2fs complete (%.1fs for frame, %.1fs elapsed)",
                path.stem, index, len(video.times), moment,
                perf_counter() - frame_started, perf_counter() - started,
            )
        decode_tracks(video, tracks)
        logger.info("Video %s: frame probing complete in %.1fs", path.stem, perf_counter() - started)
        return Reconstruction(video, tracks, self.vlm.name)


def decode_tracks(video: DecodedVideo, tracks: dict[str, AttributeTrack]) -> None:
    for track in tracks.values():
        probabilities = np.asarray([observation.probability for observation in track.observations])
        states, posterior = decode_binary(probabilities, switch_probabilities(video.times, track.probe.dwell))
        track.posterior = posterior.tolist()
        for segment in segments(states, posterior):
            first, last = segment.first, segment.last
            start = float((video.times[first - 1] + video.times[first]) / 2) if first > 0 else 0.0
            end = float((video.times[last] + video.times[last + 1]) / 2) if last + 1 < len(video.times) else video.duration
            track.segments.append(replace(segment, start=start, end=end))

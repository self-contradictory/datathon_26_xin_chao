"""Perception reconstructor: VLM probes + zoomed region probes + body keypoints + local patch motion.

observe() gathers the expensive raw evidence for one video; reconstruct() fuses it into the
attribute tracks the timeline builder already consumes. The offline tuning scripts call
reconstruct() on cached observations, so the API and the evaluation share one code path.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from backend.perception.features import FeatureConfig, Signals, compute_signals
from backend.perception.fusion import FusionConfig, fuse, resample_probe
from backend.perception.motion import PatchMotion, patch_motion
from backend.perception.pose import PoseEstimator, PoseSequence, detect_people
from backend.perception.regions import CONTEXT, RATES, REGION_PROBES, TOKENS, crop
from backend.perception.scene import Scene, locate
from backend.reconstruction.decode import Observation
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, Reconstructor, decode_tracks
from backend.reconstruction.probes import PERCEPTION_PROBES, PROBES, SCENE_CONTEXT
from backend.reconstruction.video import DecodedVideo, decode
from backend.reconstruction.vlm import QuestionVLM

type Series = dict[str, tuple[np.ndarray, np.ndarray]]


@dataclass(slots=True)
class PerceptionConfig:
    grid_fps: float = 2.0
    base_fps: float = 1.0
    base_tokens: int = 256
    base_crop: bool = False
    pose_fps: float = 4.0
    motion_fps: float = 10.0
    dwell: dict[str, float] = field(default_factory=dict)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    use_regions: bool = True
    use_cv: bool = True


@dataclass(slots=True)
class Observations:
    video: DecodedVideo
    base: Series
    regions: Series
    scene: Scene | None = None
    pose: PoseSequence | None = None
    motion: PatchMotion | None = None
    observer_model: str = ""


def _probe_series(vlm: QuestionVLM, video: DecodedVideo, fps: float, tokens: int, box) -> Series:
    keys = [probe.key for probe in PROBES]
    times, values = [], {key: [] for key in keys}
    due = 0.0
    for moment in video.times:
        if moment + 1e-6 < due:
            continue
        due = moment + 1.0 / fps - 0.25 / video.sample_fps
        image = video.frame_at(moment)
        answers = vlm.probe(crop(image, box) if box else image, [p.question for p in PROBES], SCENE_CONTEXT, tokens)
        times.append(float(moment))
        for key, value in zip(keys, answers, strict=True):
            values[key].append(value)
    return {key: (np.asarray(times), np.asarray(values[key])) for key in keys}


def _region_series(vlm: QuestionVLM, video: DecodedVideo, scene: Scene) -> Series:
    boxes = scene.regions
    data = {probe.key: ([], []) for probes in REGION_PROBES.values() for probe in probes}
    due = dict.fromkeys(REGION_PROBES, 0.0)
    for moment in video.times:
        frame = None
        for region, probes in REGION_PROBES.items():
            if moment + 1e-6 < due[region]:
                continue
            due[region] = moment + 1.0 / RATES[region] - 0.25 / video.sample_fps
            frame = video.frame_at(moment) if frame is None else frame
            answers = vlm.probe(crop(frame, boxes[region]), [p.question for p in probes], CONTEXT, TOKENS[region])
            for probe, value in zip(probes, answers, strict=True):
                data[probe.key][0].append(float(moment))
                data[probe.key][1].append(value)
    return {key: (np.asarray(t), np.asarray(v)) for key, (t, v) in data.items() if t}


def observe(path: Path, vlm: QuestionVLM, estimator: PoseEstimator | None,
            config: PerceptionConfig = PerceptionConfig()) -> Observations:
    video = decode(path, config.grid_fps)
    scene = locate(vlm, path) if config.use_regions or config.use_cv else None
    base_box = scene.regions["active"] if scene is not None and config.base_crop else None
    base = _probe_series(vlm, video, config.base_fps, config.base_tokens, base_box)
    regions = _region_series(vlm, video, scene) if config.use_regions else {}
    pose = detect_people(path, estimator, config.pose_fps) if config.use_cv and estimator else None
    motion = patch_motion(path, config.motion_fps) if config.use_cv else None
    return Observations(video, base, regions, scene, pose, motion, vlm.name)


def reconstruct(observations: Observations, config: PerceptionConfig = PerceptionConfig()) -> Reconstruction:
    video = observations.video
    grid = video.times
    base = {key: resample_probe(t, v, grid) for key, (t, v) in observations.base.items()}
    regions = ({key: resample_probe(t, v, grid) for key, (t, v) in observations.regions.items()}
               if config.use_regions else {})
    signals: Signals | None = None
    if config.use_cv and observations.pose is not None and observations.motion is not None:
        signals = compute_signals(observations.scene, observations.pose, observations.motion, config.features,
                                  video.height / video.width)
    probes = [replace(probe, dwell=config.dwell.get(probe.key, probe.dwell)) for probe in PERCEPTION_PROBES]
    fused = fuse(grid, base, regions, signals, [probe.key for probe in probes], config.fusion)
    tracks = {probe.key: AttributeTrack(probe, [Observation(float(t), float(p))
                                                for t, p in zip(grid, fused[probe.key], strict=True)])
              for probe in probes}
    decode_tracks(video, tracks)
    return Reconstruction(video, tracks, observations.observer_model)


class PerceptionReconstructor(Reconstructor):
    """Drop-in replacement for Reconstructor used by the API analyzer."""

    def __init__(self, vlm: QuestionVLM, config: PerceptionConfig = PerceptionConfig(),
                 pose_device: str | None = None) -> None:
        super().__init__(vlm, config.base_fps, config.base_tokens)
        self.config = config
        self.estimator = PoseEstimator(pose_device) if config.use_cv else None

    def run(self, path: Path) -> Reconstruction:
        return reconstruct(observe(path, self.vlm, self.estimator, self.config), self.config)

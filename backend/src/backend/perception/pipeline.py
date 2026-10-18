"""Perception reconstructor: VLM probes + zoomed region probes + body keypoints + local patch motion.

observe() gathers the expensive raw evidence for one video; reconstruct() fuses it into the
attribute tracks the timeline builder already consumes. The offline tuning scripts call
reconstruct() on cached observations, so the API and the evaluation share one code path.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path
import logging

import numpy as np

from backend.perception.features import FeatureConfig, Signals, compute_signals
from backend.perception.fusion import FusionConfig, fuse, resample_probe
from backend.perception.motion import PatchMotion, patch_motion
from backend.perception.pose import PoseEstimator, PoseSequence, detect_people
from backend.perception.regions import RATES, REGION_PROBES, TOKENS, crop, region_view
from backend.perception.scene import Scene, locate
from backend.reconstruction.decode import Observation
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, Reconstructor, decode_tracks
from backend.reconstruction.probes import PERCEPTION_PROBES, PROBES, SCENE_CONTEXT
from backend.reconstruction.video import DecodedVideo, decode
from backend.reconstruction.vlm import QuestionVLM

logger = logging.getLogger(__name__)

type Series = dict[str, tuple[np.ndarray, np.ndarray]]

# States a zoomed crop answers with 3-5x the full frame's fusion weight. Asking the full frame as well cost
# about a third of its tokens; dropping them kept every 32B verdict and raised timeline F1 (58.0% to 59.7%).
CROP_KEYS = {"key_in_safe", "stamps_on_desk", "personal_items", "food_on_desk", "screen_on", "safe_open",
             "counting_cash", "door_open"}
FRAME_PROBES = tuple(probe for probe in PROBES if probe.key not in CROP_KEYS)


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


def _probe_series(vlm: QuestionVLM, video: DecodedVideo, fps: float, tokens: int, box,
                  probes: tuple = PROBES) -> Series:
    keys = [probe.key for probe in probes]
    times, values = [], {key: [] for key in keys}
    due = 0.0
    for moment in video.times:
        if moment + 1e-6 < due:
            continue
        due = moment + 1.0 / fps - 0.25 / video.sample_fps
        image = video.frame_at(moment)
        logger.info("Video %s: full-frame probes at %.1f/%.1fs", video.path.stem, moment, video.duration)
        answers = vlm.probe(crop(image, box) if box else image, [p.question for p in probes], SCENE_CONTEXT, tokens)
        times.append(float(moment))
        for key, value in zip(keys, answers, strict=True):
            values[key].append(value)
    return {key: (np.asarray(times), np.asarray(values[key])) for key in keys}


def _region_series(vlm: QuestionVLM, video: DecodedVideo, scene: Scene) -> Series:
    boxes = scene.regions
    data = {probe.key: ([], []) for probes in REGION_PROBES.values() for probe in probes}
    due = dict.fromkeys(REGION_PROBES, 0.0)
    for index, moment in enumerate(video.times):
        frame = None
        for region, probes in REGION_PROBES.items():
            if moment + 1e-6 < due[region]:
                continue
            due[region] = moment + 1.0 / RATES[region] - 0.25 / video.sample_fps
            frame = video.frame_at(moment) if frame is None else frame
            logger.info("Video %s: %s region probes at %.1f/%.1fs", video.path.stem, region, moment, video.duration)
            view = region_view(video, index, region, boxes[region], frame)
            answers = vlm.probe(view.pop("image"), [p.question for p in probes], tokens=TOKENS[region], **view)
            for probe, value in zip(probes, answers, strict=True):
                data[probe.key][0].append(float(moment))
                data[probe.key][1].append(value)
    return {key: (np.asarray(t), np.asarray(v)) for key, (t, v) in data.items() if t}


def observe(path: Path, vlm: QuestionVLM, estimator: PoseEstimator | None,
            config: PerceptionConfig = PerceptionConfig()) -> Observations:
    logger.info("Video %s: decoding", path.stem)
    video = decode(path, config.grid_fps)
    logger.info("Video %s: decoded %.1fs, %s frames; scene grounding starts", path.stem, video.duration, len(video.times))
    scene = locate(vlm, path) if config.use_regions or config.use_cv else None
    base_box = scene.regions["active"] if scene is not None and config.base_crop else None
    base = _probe_series(vlm, video, config.base_fps, config.base_tokens, base_box,
                         FRAME_PROBES if config.use_regions else PROBES)
    regions = _region_series(vlm, video, scene) if config.use_regions else {}
    logger.info("Video %s: pose estimation starts on %s", path.stem, getattr(estimator, "device", "disabled"))
    pose = detect_people(path, estimator, config.pose_fps) if config.use_cv and estimator else None
    logger.info("Video %s: local motion starts", path.stem)
    motion = patch_motion(path, config.motion_fps) if config.use_cv else None
    logger.info("Video %s: perception complete", path.stem)
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

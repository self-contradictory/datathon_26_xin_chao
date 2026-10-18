"""Score the fused perception pipeline offline from cached probes, pose, motion and scene layout.

Example:
    .venv/bin/python -B eval/tuning/fused_bench.py --base base-full --regions regions --cv
"""
import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from backend.perception.hands import hand_evidence
from backend.perception.motion import PatchMotion
from backend.perception.pipeline import Observations, PerceptionConfig, reconstruct
from backend.perception.pose import PoseSequence
from backend.perception.scene import Scene
from backend.reconstruction.pipeline import Reconstruction
from backend.reconstruction.video import DecodedVideo
from bench import ORIGINAL, judge
from common import CACHE, VIDEOS, expected, metrics, score_video, write_json
from timeline_eval import ANNOTATIONS, score as score_timeline


@dataclass
class Experiment:
    name: str
    base: str = "base-full"
    regions: str | None = None
    config: PerceptionConfig = field(default_factory=lambda: PerceptionConfig(use_regions=False, use_cv=False))
    registry: object = None


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


_observations: dict[tuple, Observations] = {}


def observations(stem: str, base_name: str, region_name: str | None, grid_fps: float) -> Observations | None:
    key = (stem, base_name, region_name, grid_fps)
    if key in _observations:
        return _observations[key]
    base = _json(CACHE / "probes" / base_name / f"{stem}.json")
    if base is None:
        return None
    duration, native = base["duration"], base["native_fps"]
    grid = np.arange(0.0, duration - 1e-3, 1.0 / grid_fps)
    indices = [min(int(round(t * native)), int(duration * native) - 1) for t in grid]
    video = DecodedVideo(VIDEOS / base["video"], duration, native, base["width"], base["height"],
                         grid_fps, grid, indices, [])
    times = np.asarray(base["times"])
    series = {k: (times, np.asarray(v)) for k, v in base["probabilities"].items()}
    # Several region caches can be layered ("regions+regions2+hands[id_document]"); later ones
    # override keys, and a bracketed list keeps only those keys from that cache.
    regions = {}
    for layer in (region_name or "").split("+"):
        name, _, keep = layer.partition("[")
        keep = set(keep.rstrip("]").split(",")) if keep else None
        region = _json(CACHE / "probes" / name / f"{stem}.json") if name else None
        if region:
            layered = hand_evidence({k: (np.asarray(v["times"]), np.asarray(v["values"]))
                                     for k, v in region["series"].items() if v["times"]})
            regions |= {k: v for k, v in layered.items() if keep is None or k in keep}
    scene = _json(CACHE / "scene" / f"{stem}.json")
    pose = _json(CACHE / "pose" / f"{stem}.json")
    motion = CACHE / "motion" / f"{stem}.npz"
    result = Observations(video, series, regions, Scene.from_json(scene) if scene else None,
                          PoseSequence.from_json(pose) if pose else None,
                          PatchMotion.load(motion) if motion.exists() else None, base["model"])
    _observations[key] = result
    return result


def build(experiment: Experiment, stem: str) -> Reconstruction | None:
    observed = observations(stem, experiment.base, experiment.regions, experiment.config.grid_fps)
    return reconstruct(observed, experiment.config) if observed is not None else None


def run(experiment: Experiment, verbose: bool = True, save: bool = True) -> dict:
    rows, decoded, durations = [], {}, {}
    for video in expected():
        stem = Path(video).stem
        recon = build(experiment, stem)
        if recon is None:
            continue
        findings, _ = judge(recon, experiment.registry)
        if stem in ANNOTATIONS:
            decoded[stem] = {key: [(s.start, s.end, s.value) for s in track.segments]
                             for key, track in recon.tracks.items()}
            durations[stem] = recon.video.duration
        row = score_video(video, findings)
        row["findings"] = findings
        rows.append(row)
    summary = {"name": experiment.name, "metrics": metrics(rows),
               "timeline": score_timeline(decoded, durations), "rows": rows}
    if save:
        write_json(CACHE / "results" / f"{experiment.name}.json", summary)
    if verbose:
        from bench import report
        report(summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="fused")
    parser.add_argument("--base", default="base-full")
    parser.add_argument("--regions")
    parser.add_argument("--cv", action="store_true")
    parser.add_argument("--original-rules", action="store_true")
    args = parser.parse_args()
    config = PerceptionConfig(use_regions=bool(args.regions), use_cv=args.cv)
    run(Experiment(args.name, args.base, args.regions, config, ORIGINAL if args.original_rules else None))

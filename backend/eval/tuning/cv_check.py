"""Compare raw CV signals with the timeline annotations (frame-level), per attribute."""
import json
import sys

import numpy as np

from backend.perception.features import FeatureConfig, compute_signals
from backend.perception.motion import PatchMotion
from backend.perception.pose import PoseSequence
from backend.perception.scene import Scene
from common import CACHE
from timeline_eval import ANNOTATIONS, truth

KEYS = ["room_occupied", "customer_present", "cashier_at_station", "person_in_doorway", "at_safe"]


def main(config=FeatureConfig(), verbose=True):
    pooled = {}
    for stem in ANNOTATIONS:
        if not (CACHE / "pose" / f"{stem}.json").exists():
            continue
        scene = Scene.from_json(json.loads((CACHE / "scene" / f"{stem}.json").read_text()))
        pose = PoseSequence.from_json(json.loads((CACHE / "pose" / f"{stem}.json").read_text()))
        signals = compute_signals(scene, pose, PatchMotion.load(CACHE / "motion" / f"{stem}.npz"), config)
        for key in KEYS:
            answer = truth(stem, key, signals.times)
            if answer is None:
                continue
            labels, valid = answer
            predicted = signals.values[key] >= 0.5
            c = np.array([np.sum(valid & labels & predicted), np.sum(valid & ~labels & ~predicted),
                          np.sum(valid & ~labels & predicted), np.sum(valid & labels & ~predicted)])
            pooled.setdefault(key, np.zeros(4, int))
            pooled[key] += c
            if verbose and (c[2] + c[3]) > 0.15 * c.sum():
                print(f"  {stem} {key}: tp {c[0]} tn {c[1]} fp {c[2]} fn {c[3]}")
    for key, (tp, tn, fp, fn) in pooled.items():
        bal = np.mean([v for v in (tp / (tp + fn) if tp + fn else None, tn / (tn + fp) if tn + fp else None) if v is not None])
        print(f"{key:20s} balanced {bal:.3f}  tp {tp} tn {tn} fp {fp} fn {fn}")


if __name__ == "__main__":
    main()

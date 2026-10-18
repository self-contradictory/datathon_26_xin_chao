"""Tune a small set of interpretable parameters and report in-sample and 7-fold held-out accuracy.

    .venv/bin/python -B eval/tuning/run_tuning.py --regions regions+regions2+hands
"""
import argparse
import json

from backend.perception.features import FeatureConfig
from backend.perception.fusion import FusionConfig
from backend.perception.pipeline import PerceptionConfig
from backend.reconstruction import derived, graph
from calibrate import thresholds
from common import CACHE, write_json
from fused_bench import Experiment, run
from tune import Tuner, dwell, module, offset

OFFSETS = ("counting_cash", "id_document", "handover", "cash_on_desk", "safe_open", "door_open", "at_safe",
           "key_in_safe", "screen_unlocked", "stamps_on_desk", "personal_items", "bag_on_desk", "eating")


def knobs():
    return [offset(key) for key in OFFSETS] + [
        module("left_open_sec", derived, "LEFT_OPEN_SEC", (2.0, 3.0, 4.0, 6.0), 3.0),
        module("known_confidence", graph, "KNOWN_CONFIDENCE", (0.5, 0.6, 0.7), 0.6),
        module("event_confidence", graph, "EVENT_CONFIDENCE", (0.6, 0.7, 0.8, 0.9), 0.8),
        dwell("counting_cash", (3.0, 6.0, 10.0), 6.0),
        dwell("id_document", (2.0, 3.0, 6.0), 3.0),
    ]


def base_config(regions: str) -> PerceptionConfig:
    return PerceptionConfig(use_regions=True, use_cv=True, features=FeatureConfig(),
                            fusion=FusionConfig(base_bias=thresholds("base-full"), region_bias=thresholds(regions)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regions", default="regions")
    parser.add_argument("--folds", type=int, default=7)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--label", default="regions")
    args = parser.parse_args()
    tuner = Tuner(Experiment("tune", "base-full", args.regions, base_config(args.regions)), knobs())
    result = tuner.validate(args.folds, args.rounds)
    print(json.dumps({k: v for k, v in result.items() if k != "held_out"}, indent=1, default=str))
    write_json(CACHE / "results" / f"tuning-{args.label}.json", json.loads(json.dumps(result, default=str)))
    # Re-run the chosen state for the full report.
    config = tuner.config(result["state"])
    run(Experiment(f"E5-tuned-{args.label}", "base-full", args.regions, config))

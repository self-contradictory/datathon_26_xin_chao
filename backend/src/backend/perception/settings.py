"""Tuned perception parameters, keyed by observer model.

The probe calibration (per-question logit decision points) is model-specific. A model without an
entry runs uncalibrated; eval/tuning/calibrate.py derives an entry label-free from cached probes.
"""
import json
from dataclasses import fields
from pathlib import Path

from backend.perception.features import FeatureConfig
from backend.perception.fusion import FusionConfig
from backend.perception.pipeline import PerceptionConfig

CALIBRATION = Path(__file__).with_name("calibration.json")


def load_config(model_name: str, path: Path = CALIBRATION) -> PerceptionConfig:
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    entry = entries.get(model_name, {})
    features = FeatureConfig(**{f.name: entry["features"][f.name] for f in fields(FeatureConfig)
                                if f.name in entry.get("features", {})})
    fusion = FusionConfig(
        base_bias=entry.get("base_bias", {}), region_bias=entry.get("region_bias", {}),
        offsets=entry.get("offsets", {}),
        weights={key: tuple(value) for key, value in entry.get("weights", {}).items()},
    )
    return PerceptionConfig(dwell=entry.get("dwell", {}), fusion=fusion, features=features,
                            **{key: entry[key] for key in ("grid_fps", "base_fps", "base_tokens", "base_crop",
                                                            "pose_fps", "motion_fps") if key in entry})

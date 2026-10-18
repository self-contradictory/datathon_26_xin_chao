"""Fuse VLM probe scores, zoomed region probes and body/motion signals into one score per state key.

Every source is resampled onto a common grid. Scores are combined in logit space with fixed,
per-key source weights: people-centred states lean on pose, object states on the zoomed crops,
and the full-frame probes stay as a weaker prior.
"""
from dataclasses import dataclass, field

import numpy as np

from backend.perception.features import Signals

EPS = 1e-4


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def resample_probe(times: np.ndarray, values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Linear interpolation in logit space, held constant beyond the first and last sample."""
    return sigmoid(np.interp(grid, times, logit(np.asarray(values, float))))


@dataclass(slots=True)
class FusionConfig:
    # Per-source logit decision points (label-free Otsu calibration), subtracted before fusion.
    base_bias: dict[str, float] = field(default_factory=dict)
    region_bias: dict[str, float] = field(default_factory=dict)
    # Extra logit offset per key after fusion.
    offsets: dict[str, float] = field(default_factory=dict)
    # Weight of each source per key: base full-frame probe, region probe, CV signal.
    weights: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    # Logit given to a binary CV signal that fires (and its negative when it does not).
    cv_strength: float = 4.0
    # Scale of the negative evidence when a CV signal does not fire: a missed wrist or an
    # occluded hand is weak evidence of absence.
    cv_absence: dict[str, float] = field(default_factory=lambda: dict(CV_ABSENCE))


# Extra full-frame probes that are evidence for a key: being seated at the desk is the most
# reliable sign that the cashier is at the station.
ALIASES = {"cashier_at_station": ("cashier_seated",)}

# Keys whose CV signal is binary evidence of the state (1 = present).
CV_KEYS = {
    "room_occupied": "room_occupied", "customer_present": "customer_present",
    "cashier_at_station": "cashier_at_station", "person_in_doorway": "person_in_doorway",
    "at_safe": "at_safe", "using_computer": "using_computer",
    "eating": "hand_to_mouth", "counting_cash": "hands_on_desk", "handover": "hands_close",
    "door_open": "door_open",
}

AGREE = {"door_open"}

UNSEEN_IN_DARK = {"door_open", "safe_open", "key_in_safe", "cash_on_desk", "bag_on_desk", "stamps_on_desk",
                  "personal_items", "food_on_desk"}

CV_ABSENCE = {"at_safe": 0.25, "using_computer": 0.25, "eating": 0.0, "counting_cash": 0.0, "handover": 0.0}

DEFAULT_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "room_occupied": (0.3, 0.0, 1.0),
    "customer_present": (0.0, 0.0, 1.0),
    "cashier_at_station": (1.0, 0.0, 0.5),
    "person_in_doorway": (0.3, 0.5, 1.0),
    "at_safe": (0.2, 0.5, 1.0),
    "using_computer": (0.5, 0.0, 0.5),
    "safe_open": (0.3, 1.0, 0.0),
    "key_in_safe": (0.2, 1.0, 0.0),
    "screen_on": (0.3, 1.0, 0.0),
    "cash_on_desk": (0.3, 1.0, 0.0),
    "bag_on_desk": (0.3, 1.0, 0.0),
    "food_on_desk": (0.3, 1.0, 0.0),
    "stamps_on_desk": (0.2, 1.0, 0.0),
    "personal_items": (0.2, 1.0, 0.0),
    "counting_cash": (1.0, 0.5, 0.2),
    "handover": (1.0, 0.5, 0.2),
    "id_document": (0.3, 1.0, 0.0),
    "eating": (0.5, 1.0, 0.2),
    "phone": (0.5, 1.0, 0.0),
    "door_open": (0.3, 0.5, 1.0),
    "screen_unlocked": (0.0, 1.0, 0.0),
}


def fuse(grid: np.ndarray, base: dict[str, np.ndarray], regions: dict[str, np.ndarray],
         signals: Signals | None, keys: list[str], config: FusionConfig = FusionConfig()) -> dict[str, np.ndarray]:
    """base and regions are already resampled onto grid; returns a probability series per key."""
    weights = DEFAULT_WEIGHTS | config.weights
    cv = {}
    if signals is not None:
        for key, name in CV_KEYS.items():
            cv[key] = signals.at(name, grid, "mean", 0.25)
    lit = signals.at("lit", grid, "mean", 0.25) if signals is not None else None
    fused = {}
    for key in keys:
        wb, wr, wc = weights.get(key, (1.0, 0.0, 0.0))
        total = np.zeros(len(grid))
        norm = 0.0
        if key in base and wb > 0:
            total += wb * (logit(base[key]) - config.base_bias.get(key, 0.0))
            norm += wb
            for alias in ALIASES.get(key, ()):
                if alias in base:
                    total += wb * (logit(base[alias]) - config.base_bias.get(alias, 0.0))
                    norm += wb
        if key in regions and wr > 0:
            total += wr * (logit(regions[key]) - config.region_bias.get(key, 0.0))
            norm += wr
        if key in cv and wc > 0:
            evidence = 2 * cv[key] - 1
            total += wc * config.cv_strength * np.where(evidence < 0, config.cv_absence.get(key, 1.0) * evidence,
                                                        evidence)
            norm += wc
        if norm == 0:
            fused[key] = np.full(len(grid), 0.5)
            continue
        fused[key] = sigmoid(total / norm + config.offsets.get(key, 0.0))
        if key in AGREE and key in regions and key in cv:
            # Both views must agree: the zoomed crop judges the door itself, the patch change
            # judges it against the start of the video (wrong when the door starts open).
            crop = sigmoid(logit(regions[key]) - config.region_bias.get(key, 0.0) + config.offsets.get(key, 0.0))
            fused[key] = np.minimum(crop, cv[key])
        if signals is not None and key in UNSEEN_IN_DARK:
            # With the lights off only a lit screen is visible; other object states are unknown.
            fused[key] = np.where(lit >= 0.5, fused[key], 0.5)
    return fused

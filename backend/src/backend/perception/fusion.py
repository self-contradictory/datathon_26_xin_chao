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
    # The full-frame question separates a customer at the desk on 32B (AUC 1.000 on 5 videos) where pose
    # (AUC 0.83) hovers near 0.5 and split one Х-16 visit in two. Weighted below pose, it decides only
    # when pose is unsure, which keeps the 2B results (42 videos) unchanged.
    "customer_present": (0.5, 0.0, 1.0),
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
    # Hand actions: the zoomed hands crop sees the banknotes, the full frame mostly does not
    # (32B counting AUC: full frame 0.54, hands crop 0.77, 3-frame hands clip 0.94).
    "counting_cash": (0.2, 1.0, 0.2),
    "handover": (0.5, 1.0, 0.2),
    "cash_from_customer": (0.5, 1.0, 0.0),
    "cash_to_customer": (0.5, 1.0, 0.0),
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
    regions, calibrated = _left_items(regions, config.region_bias)
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
            total += wr * (logit(regions[key]) - (0.0 if key in calibrated else config.region_bias.get(key, 0.0)))
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
    _explain_away(fused, regions)
    return fused


LEFT_KINDS = ("cash_on_desk", "bag_on_desk", "personal_items")


def _calibrate(values: np.ndarray, bias: float) -> np.ndarray:
    return sigmoid(logit(values) - bias)


def _left_items(regions: dict[str, np.ndarray], bias: dict[str, float]) -> tuple[dict[str, np.ndarray], set[str]]:
    """Something left on the desk that is not cash, a bag or a personal item is a stamp, a seal or a
    document: 32B does not name round self-inking stamps as stamps, but it does see that they are there.
    The answers are compared after calibration: on 32B the generic question scores 0.96 on a clear desk
    (Х-23) and 1.00 with stamps on it (Х-24), and only its own threshold (p 0.97) tells them apart.
    Returns the regions and the keys that are already calibrated."""
    if "desk_items" not in regions:
        return regions, set()
    shifted = {key: _calibrate(regions[key], bias.get(key, 0.0)) for key in (*LEFT_KINDS, "desk_items", "stamps_on_desk")
               if key in regions}
    named = np.max([shifted[key] for key in LEFT_KINDS if key in shifted] or [np.zeros(len(shifted["desk_items"]))],
                   axis=0)
    other = shifted["desk_items"] * (1 - named)
    return regions | {"stamps_on_desk": np.maximum(shifted.get("stamps_on_desk", other), other)}, {"stamps_on_desk"}


# A card or banknotes held up to the face look like a phone call or a drink to the VLM: on Х-3 and Х-16
# the cashier checks the customer's ID card and every view answered yes to the phone question, which raised
# CD25 on clean videos. A phone or food counts only while the hands are not holding an ID card or money.
HELD_ITEMS = ("id_document", "cash_in_hands")
EXPLAINED = ("phone", "eating")


def _explain_away(fused: dict[str, np.ndarray], regions: dict[str, np.ndarray]) -> None:
    held = [source[key] for key in HELD_ITEMS for source in (fused, regions) if key in source]
    if not held:
        return
    holding = np.max(held, axis=0)
    for key in EXPLAINED:
        if key in fused:
            fused[key] = fused[key] * (1 - holding)

"""Zoomed region probes: each grounded crop gets the yes/no questions it can answer best.

Small objects (banknotes, stamps, a key, a lit screen) cover a few dozen pixels in the full frame.
Cropping the region and resizing it to the token budget lets the VLM see them (ViCrop, ICLR 2025).
"""
from dataclasses import dataclass

import numpy as np

from backend.perception.scene import Box

CONTEXT = "This is a zoomed crop from a ceiling security camera above a bank cash desk."


@dataclass(frozen=True, slots=True)
class RegionProbe:
    key: str
    question: str


REGION_PROBES: dict[str, tuple[RegionProbe, ...]] = {
    "desk": (
        RegionProbe("cash_on_desk", "Are banknotes or a stack of money lying on the desk?"),
        RegionProbe("bag_on_desk", "Is there a bag or package lying on the desk?"),
        # Asked specifically. The generic "any small objects left on the desktop" wording suited 2B,
        # but Qwen3-VL-32B answered yes to it on 48% of frames of the clean video Х-3 and on 99% of
        # Х-15 (the bag), which raised false CD08 alarms; this wording stayed below 0.05 on both.
        RegionProbe("stamps_on_desk", "Is a rubber stamp, a stamp pad or a seal lying on the desk?"),
        RegionProbe("food_on_desk", "Is there food or a drink on the desk?"),
        RegionProbe("personal_items", "Is a handbag, purse, wallet, coat or jacket lying on the desk?"),
    ),
    "desk_hands": (
        RegionProbe("counting_cash", "Is someone counting banknotes?"),
        RegionProbe("handover", "Is money or a document being passed from one person's hand to another person's hand?"),
        RegionProbe("id_document", "Is someone holding or showing an ID card or passport?"),
        RegionProbe("eating", "Is someone eating or drinking?"),
        RegionProbe("phone", "Is someone using a mobile phone?"),
        RegionProbe("cash_in_hands", "Is someone holding banknotes in their hands?"),
    ),
    "safe": (
        RegionProbe("safe_open", "Is the safe door open?"),
        RegionProbe("key_in_safe", "Is a key inserted in the safe's lock?"),
        RegionProbe("at_safe", "Is a person reaching into or standing at the safe?"),
    ),
    "laptop": (
        RegionProbe("screen_on", "Is the laptop screen lit?"),
        RegionProbe("screen_unlocked", "Does the laptop screen show an open document or program window?"),
        RegionProbe("laptop_closed", "Is the laptop lid closed?"),
    ),
    "door": (
        RegionProbe("door_open", "Is the glass door open?"),
        RegionProbe("person_in_doorway", "Is a person walking through the doorway?"),
    ),
}

TOKENS = {"desk": 256, "desk_hands": 256, "safe": 160, "laptop": 128, "door": 160}
# Samples per second: hand actions are short, object states change slowly.
RATES = {"desk": 1.0, "desk_hands": 1.0, "safe": 0.5, "laptop": 0.5, "door": 0.5}


def crop(image: np.ndarray, box: Box) -> np.ndarray:
    h, w = image.shape[:2]
    x0, y0, x1, y1 = box
    return image[round(y0 * h):max(round(y0 * h) + 2, round(y1 * h)),
                 round(x0 * w):max(round(x0 * w) + 2, round(x1 * w))]

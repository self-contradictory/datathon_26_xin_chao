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
        # Anything left out at all. 32B never answered yes to the stamp question on Х-24, where two
        # round self-inking stamps stand on the desk (it took them for cups), but answered yes to this one
        # on every frame. fusion.left_items turns what is not cash, a bag or a personal item into stamps.
        RegionProbe("desk_items", "Are any small objects left on the desktop besides the telephone, the laptop "
                                  "and the counting machine?"),
    ),
    # Three frames 0.5 s apart: counting and handing over are movements, and one still frame of a hand
    # holding banknotes looks the same as counting them (32B counting AUC 0.94 on the clip, 0.77 on one crop).
    "desk_hands": (
        RegionProbe("counting_cash", "Across these frames, is someone counting banknotes by hand?"),
        RegionProbe("handover", "Across these frames, is money or a document passed from one person's hand to "
                                "another person's hand?"),
        RegionProbe("cash_from_customer", "Across these frames, is the customer handing banknotes to the cashier?"),
        RegionProbe("cash_to_customer", "Across these frames, is the cashier handing banknotes to the customer?"),
        RegionProbe("id_document", "Across these frames, is someone showing or holding an identity card or passport?"),
        RegionProbe("eating", "Across these frames, is someone eating or drinking?"),
        RegionProbe("phone", "Across these frames, is someone using a mobile phone?"),
        RegionProbe("cash_in_hands", "Across these frames, is someone holding banknotes?"),
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

# Image tokens per crop (per frame for a clip).
TOKENS = {"desk": 256, "desk_hands": 160, "safe": 160, "laptop": 128, "door": 160}
# Samples per second: hand actions are short, object states change slowly (the timeline HMM holds a desk
# object for 15-20 s, so one look every 2 s loses nothing and halves the desk cost).
RATES = {"desk": 0.5, "desk_hands": 1.0, "safe": 0.5, "laptop": 0.5, "door": 0.5}
# Regions asked about a short clip instead of one frame: offsets in analysis-grid steps (0.5 s at 2 fps).
CLIPS = {"desk_hands": (-1, 0, 1)}
CLIP_CONTEXT = ("These are {n} consecutive zoomed crops, 0.5 seconds apart, from a ceiling security camera above a "
                "bank cash desk. The cashier is the employee on the laptop side of the desk; the customer is on the "
                "other side.")


def crop(image: np.ndarray, box: Box) -> np.ndarray:
    h, w = image.shape[:2]
    x0, y0, x1, y1 = box
    return image[round(y0 * h):max(round(y0 * h) + 2, round(y1 * h)),
                 round(x0 * w):max(round(x0 * w) + 2, round(x1 * w))]


def region_view(video, index: int, region: str, box: Box, frame: np.ndarray | None = None) -> dict:
    """probe() arguments for one region at grid sample `index`: one crop, or a clip of crops with captions."""
    offsets = CLIPS.get(region)
    if offsets is None:
        image = frame if frame is not None else video.frame_at(video.times[index])
        return {"image": crop(image, box), "context": CONTEXT}
    picks = [min(len(video.times) - 1, max(0, index + offset)) for offset in offsets]
    return {"image": [crop(video.frame_at(video.times[pick]), box) for pick in picks],
            "context": CLIP_CONTEXT.format(n=len(picks)),
            "captions": [f"Frame {n} ({video.times[pick]:.1f}s):" for n, pick in enumerate(picks, start=1)]}

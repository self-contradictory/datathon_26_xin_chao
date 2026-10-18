"""Per-video scene layout: where the desk, safe, laptop and door are, from the VLM's grounding output.

One short grounding generation per object on the median background frame. A box that cannot be
parsed falls back to the typical position in this camera setup.
"""
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import torch

from backend.reconstruction.vlm import QuestionVLM, fit_tokens

logger = logging.getLogger(__name__)

type Box = tuple[float, float, float, float]

OBJECTS = {
    "safe": "the grey metal safe",
    "laptop": "the laptop",
    "desk": "the wooden desk",
    "machine": "the banknote counting machine",
    "door_handle": "the door handle",
}

# Typical positions in the dataset camera, used only when grounding fails.
FALLBACK: dict[str, Box] = {
    "safe": (0.45, 0.30, 0.80, 0.55),
    "laptop": (0.45, 0.38, 0.65, 0.52),
    "desk": (0.10, 0.42, 0.72, 0.65),
    "machine": (0.08, 0.40, 0.30, 0.55),
    "door_handle": (0.20, 0.30, 0.27, 0.38),
}
BOX = re.compile(r"\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]")


def expand(box: Box, left: float, top: float, right: float, bottom: float) -> Box:
    """Grow a normalized box by fractions of its own width and height, clipped to the image."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    return (max(0.0, x0 - left * w), max(0.0, y0 - top * h), min(1.0, x1 + right * w), min(1.0, y1 + bottom * h))


@dataclass(slots=True)
class Scene:
    boxes: dict[str, Box]
    grounded: dict[str, bool] = field(default_factory=dict)

    @property
    def regions(self) -> dict[str, Box]:
        """Crops used for zoomed probes and local patch statistics."""
        hx0, hy0, hx1, hy1 = self.boxes["door_handle"]
        hx, hy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
        return {
            "desk": expand(self.boxes["desk"], 0.08, 0.35, 0.08, 0.0),
            "desk_hands": expand(self.boxes["desk"], 0.12, 0.9, 0.12, 0.1),
            "safe": expand(self.boxes["safe"], 0.35, 0.25, 0.25, 0.15),
            "laptop": expand(self.boxes["laptop"], 0.3, 0.3, 0.3, 0.3),
            "screen": expand(self.boxes["laptop"], -0.1, -0.05, -0.1, -0.35),
            "door": (max(0.0, hx - 0.28), max(0.0, hy - 0.30), min(1.0, hx + 0.10), min(1.0, hy + 0.16)),
            "active": (0.0, 0.0, 1.0, min(1.0, max(0.62, self.boxes["desk"][3] + 0.12))),
        }

    def to_json(self) -> dict:
        return {"boxes": self.boxes, "grounded": self.grounded}

    @classmethod
    def from_json(cls, data: dict) -> Scene:
        return cls({key: tuple(value) for key, value in data["boxes"].items()}, data.get("grounded", {}))


def median_background(path: Path, samples: int = 15) -> np.ndarray:
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    try:
        for index in np.linspace(0, max(0, count - 2), samples).astype(int):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = capture.read()
            if ok:
                frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise ValueError(f"No video frames decoded from {path}")
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


@torch.inference_mode()
def ground(model: QuestionVLM, image: np.ndarray, description: str, tokens: int = 512) -> Box | None:
    if hasattr(model, "text"):
        answer = model.text(f"Locate {description} in this image. Output its bbox_2d coordinates.",
                            [image], image_tokens=tokens, max_new_tokens=48)
        return parse_box(answer)
    content = [{"type": "image"},
               {"type": "text", "text": f"Locate {description} in this image. Output its bbox_2d coordinates."}]
    text = model._processor.apply_chat_template([{"role": "user", "content": content}], add_generation_prompt=True)
    with model._lock:
        inputs = model._image_inputs(fit_tokens(image, tokens), text)
        model._model.model.rope_deltas = None
        output = model._model.generate(**inputs, max_new_tokens=48, do_sample=False)
        model._model.model.rope_deltas = None
    answer = model._processor.batch_decode(output[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
    return parse_box(answer)


def parse_box(answer: str) -> Box | None:
    match = BOX.search(answer)
    if not match:
        return None
    x0, y0, x1, y1 = (min(1.0, max(0.0, float(v) / 1000)) for v in match.groups())
    if x1 - x0 < 0.01 or y1 - y0 < 0.01:
        return None
    return x0, y0, x1, y1


def locate(model: QuestionVLM, path: Path) -> Scene:
    background = median_background(path)
    boxes, grounded = {}, {}
    for key, description in OBJECTS.items():
        logger.info("Video %s: grounding %s", path.stem, key)
        box = ground(model, background, description)
        grounded[key] = box is not None
        boxes[key] = box or FALLBACK[key]
        logger.info("Video %s: %s grounding %s", path.stem, key, "complete" if box else "used fallback")
    return Scene(boxes, grounded)

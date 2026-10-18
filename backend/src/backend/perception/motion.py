"""Local patch motion on a fixed grid: frame difference, DIS optical flow and background difference."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

type Box = tuple[float, float, float, float]


@dataclass(slots=True)
class PatchMotion:
    times: np.ndarray
    luminance: np.ndarray
    difference: np.ndarray
    flow: np.ndarray
    background: np.ndarray

    @property
    def grid(self) -> tuple[int, int]:
        return self.luminance.shape[1:3]

    def mask(self, box: Box) -> np.ndarray:
        rows, cols = self.grid
        y = (np.arange(rows) + 0.5) / rows
        x = (np.arange(cols) + 0.5) / cols
        x0, y0, x1, y1 = box
        return ((y >= y0) & (y <= y1))[:, None] & ((x >= x0) & (x <= x1))[None, :]

    def region(self, values: np.ndarray, box: Box, reduce=np.mean) -> np.ndarray:
        """Per-sample reduction of a (T, rows, cols) array over the patches inside a normalized box."""
        mask = self.mask(box)
        if not mask.any():
            rows, cols = self.grid
            x0, y0, x1, y1 = box
            mask[min(rows - 1, int((y0 + y1) / 2 * rows)), min(cols - 1, int((x0 + x1) / 2 * cols))] = True
        return reduce(values[:, mask], axis=1)

    @property
    def magnitude(self) -> np.ndarray:
        return np.hypot(self.flow[..., 0], self.flow[..., 1])

    def save(self, path: Path) -> None:
        np.savez_compressed(path, times=self.times, luminance=self.luminance.astype(np.float16),
                            difference=self.difference.astype(np.float16), flow=self.flow.astype(np.float16),
                            background=self.background.astype(np.float16))

    @classmethod
    def load(cls, path: Path) -> PatchMotion:
        data = np.load(path)
        return cls(data["times"], *(data[key].astype(np.float32)
                                    for key in ("luminance", "difference", "flow", "background")))


def _patches(image: np.ndarray, size: int) -> np.ndarray:
    rows, cols = image.shape[0] // size, image.shape[1] // size
    trimmed = image[:rows * size, :cols * size]
    return trimmed.reshape(rows, size, cols, size, *image.shape[2:]).mean(axis=(1, 3))


def patch_motion(path: Path, fps: float = 6.0, width: int = 232, patch: int = 8) -> PatchMotion:
    """Samples the video at `fps`, downscales it to `width` pixels and averages each signal over
    `patch`-pixel squares. Flow is in analysis pixels per sample interval."""
    capture = cv2.VideoCapture(str(path))
    native = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frames, times = [], []
    next_sample, index = 0.0, 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            moment = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if moment == 0.0 and index > 0:
                moment = index / native
            if moment + 1e-6 >= next_sample:
                height = round(frame.shape[0] * width / frame.shape[1])
                gray = cv2.cvtColor(cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA),
                                    cv2.COLOR_BGR2GRAY)
                frames.append(cv2.GaussianBlur(gray, (3, 3), 0))
                times.append(moment)
                next_sample += 1.0 / fps
            index += 1
    finally:
        capture.release()
    if not frames:
        raise ValueError(f"No video frames decoded from {path}")
    stack = np.stack(frames)
    background = np.median(stack[np.linspace(0, len(stack) - 1, min(len(stack), 90)).astype(int)], axis=0)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    luminance, difference, flow, static = [], [], [], []
    previous = stack[0]
    for current in stack:
        luminance.append(_patches(current.astype(np.float32), patch))
        difference.append(_patches(cv2.absdiff(current, previous).astype(np.float32), patch))
        flow.append(_patches(dis.calc(previous, current, None), patch))
        static.append(_patches(np.abs(current.astype(np.float32) - background), patch))
        previous = current
    return PatchMotion(np.asarray(times), np.stack(luminance), np.stack(difference),
                       np.stack(flow), np.stack(static))

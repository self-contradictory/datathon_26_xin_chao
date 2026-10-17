from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(slots=True)
class DecodedVideo:
    path: Path
    duration: float
    native_fps: float
    width: int
    height: int
    sample_fps: float
    times: np.ndarray
    frame_indices: list[int]
    images: list[bytes]

    def frame_at(self, moment: float) -> np.ndarray:
        return cv2.imdecode(np.frombuffer(self.jpeg_at(moment), np.uint8), cv2.IMREAD_COLOR)

    def jpeg_at(self, moment: float) -> bytes:
        return self.images[int(np.argmin(np.abs(self.times - moment)))]


def decode(path: Path, sample_fps: float = 1.0) -> DecodedVideo:
    capture = cv2.VideoCapture(str(path))
    native_fps = capture.get(cv2.CAP_PROP_FPS)
    times, indices, images = [], [], []
    next_sample = 0.0
    index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            moment = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if moment == 0.0 and index > 0:
                moment = index / native_fps
            height, width = frame.shape[:2]
            if moment + 1e-6 >= next_sample:
                _, encoded = cv2.imencode(".jpg", frame)
                times.append(moment)
                indices.append(index)
                images.append(encoded.tobytes())
                next_sample += 1.0 / sample_fps
            index += 1
    finally:
        capture.release()
    if not images:
        raise ValueError(f"No video frames decoded from {path}")
    return DecodedVideo(
        path, moment + 1.0 / native_fps, native_fps, width, height,
        sample_fps, np.asarray(times), indices, images,
    )

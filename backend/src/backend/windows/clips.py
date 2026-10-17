from dataclasses import dataclass

import numpy as np

from backend.reconstruction.video import DecodedVideo
from backend.reconstruction.vlm import fit_tokens


@dataclass(slots=True)
class Clip:
    index: int
    start: float
    end: float
    times: list[float]
    frames: np.ndarray
    metadata: dict


def window_bounds(duration: float, window: float, stride: float) -> list[tuple[float, float]]:
    bounds, start = [], 0.0
    while True:
        end = min(duration, start + window)
        bounds.append((start, end))
        if end >= duration:
            return bounds
        start += stride


def clips(video: DecodedVideo, window: float = 6.0, stride: float = 3.0, tokens: int = 256) -> list[Clip]:
    result = []
    for index, (start, end) in enumerate(window_bounds(video.duration, window, stride)):
        chosen = [i for i, moment in enumerate(video.times) if start - 1e-6 <= moment < end - 1e-6]
        if not chosen:
            continue
        if len(chosen) % 2:
            chosen.append(chosen[-1])
        frames = np.stack([np.asarray(fit_tokens(video.frame_at(video.times[i]), tokens)) for i in chosen])
        metadata = {"fps": video.native_fps, "duration": video.duration,
                    "total_num_frames": video.frame_indices[-1] + 1,
                    "frames_indices": [video.frame_indices[i] for i in chosen]}
        result.append(Clip(index, start, end, [float(video.times[i]) for i in chosen], frames, metadata))
    return result

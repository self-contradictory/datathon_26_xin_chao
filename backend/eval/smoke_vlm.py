"""Check local model loading, image probes, JSON generation, and video input."""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from pydantic import BaseModel

from backend.reconstruction.vlm import fit_tokens
from backend.windows.clips import Clip
from backend.windows.model import WindowVLM


class Description(BaseModel):
    description: str


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="32b")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--quantization", choices=["none", "4bit"], default="4bit")
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()

    # Decode only one frame before loading the model or running the full pipeline.
    capture = cv2.VideoCapture(str(args.video))
    try:
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok:
        raise ValueError(f"Cannot read the first frame of {args.video}")

    began = time.perf_counter()
    model = WindowVLM(args.model, args.model_path, args.device, args.quantization)
    print(f"Loaded {model.name} on {model.device} in {time.perf_counter() - began:.1f}s", flush=True)
    probabilities = model.probe(
        frame, ["Is there a person visible?", "Is there a desk visible?"],
        "Look at this surveillance camera frame.", tokens=256,
    )
    description = model.structured(
        "Describe the visible scene in one short sentence.", Description, [frame], max_new_tokens=128,
    )
    # Qwen video inputs need a pair of frames. Repeating this frame tests the
    # video processor and generation path without decoding the whole video.
    frames = np.stack([np.asarray(fit_tokens(frame, 256))] * 2)
    clip = Clip(0, 0.0, 1.0, [0.0, 0.5], frames, {
        "fps": 2.0, "duration": 1.0, "total_num_frames": 2, "frames_indices": [0, 1],
    })
    video_description = model.generate("Describe this scene in one sentence.", clip, max_new_tokens=128)
    if not video_description.strip() or not all(np.isfinite(p) and 0 <= p <= 1 for p in probabilities):
        raise RuntimeError("The model returned an empty answer or invalid probabilities")
    result = {
        "status": "ok", "model": model.name, "device": model.device,
        "quantization": model.quantization, "probabilities": probabilities,
        "image_description": description.description, "video_description": video_description,
        "seconds": round(time.perf_counter() - began, 1),
    }
    if model.device.startswith("cuda"):
        result["peak_gpu_memory_gib"] = round(torch.cuda.max_memory_allocated(model.device) / 1024**3, 2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

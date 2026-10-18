"""Cache per-frame yes/no probe probabilities for every dataset video.

The cache lets the timeline and rule parameters be tuned offline without rerunning the VLM.

Baseline (the existing pipeline's first stage):
    .venv/bin/python -B eval/tuning/probe_cache.py --name base-full --fps 1 --tokens 256
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from backend.perception.scene import Scene
from backend.reconstruction.probes import PROBES, SCENE_CONTEXT
from backend.reconstruction.video import decode
from backend.reconstruction.vlm import QuestionVLM
from common import CACHE, videos, write_json


def crop(image: np.ndarray, box: tuple[float, float, float, float] | None) -> np.ndarray:
    if box is None:
        return image
    h, w = image.shape[:2]
    x0, y0, x1, y1 = box
    return image[round(y0 * h):round(y1 * h), round(x0 * w):round(x1 * w)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--model", default="2b")
    parser.add_argument("--device")
    parser.add_argument("--fps", type=float, default=1.0)
    parser.add_argument("--tokens", type=int, default=256)
    parser.add_argument("--crop", help="normalized x0,y0,x1,y1 applied to every frame")
    parser.add_argument("--scene-crop", action="store_true", help="crop each video to its grounded active region")
    parser.add_argument("--videos", nargs="*")
    args = parser.parse_args()
    box = tuple(float(v) for v in args.crop.split(",")) if args.crop else None
    out = CACHE / "probes" / args.name
    model = QuestionVLM(args.model, None, args.device)
    questions = [probe.question for probe in PROBES]
    for path in videos():
        if args.videos and path.stem not in args.videos:
            continue
        target = out / f"{path.stem}.json"
        if target.exists():
            continue
        if args.scene_crop:
            scene = json.loads((CACHE / "scene" / f"{path.stem}.json").read_text(encoding="utf-8"))
            box = Scene.from_json(scene).regions["active"]
        began = time.perf_counter()
        video = decode(path, args.fps)
        probabilities = {probe.key: [] for probe in PROBES}
        for moment in video.times:
            answers = model.probe(crop(video.frame_at(moment), box), questions, SCENE_CONTEXT, args.tokens)
            for probe, value in zip(PROBES, answers, strict=True):
                probabilities[probe.key].append(value)
        write_json(target, {
            "video": path.name, "model": model.name, "fps": args.fps, "tokens": args.tokens, "crop": box,
            "duration": video.duration, "native_fps": video.native_fps, "width": video.width,
            "height": video.height, "times": video.times.tolist(), "frame_indices": video.frame_indices,
            "probabilities": probabilities, "seconds": time.perf_counter() - began,
        })
        print(f"{args.name} {path.name}: {len(video.times)} frames in {time.perf_counter() - began:.1f}s", flush=True)


if __name__ == "__main__":
    main()

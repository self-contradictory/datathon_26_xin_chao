"""Cache pose-guided hand-zoom probes (ID card, banknotes, counting) for every video."""
import argparse
import json
import time

import numpy as np

from backend.perception.hands import HAND_PROBES, HAND_TOKENS, hand_box
from backend.perception.pose import PoseSequence
from backend.perception.regions import CONTEXT, crop
from backend.perception.scene import Scene
from backend.reconstruction.video import decode
from backend.reconstruction.vlm import QuestionVLM
from common import CACHE, videos, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="hands")
    parser.add_argument("--model", default="2b")
    parser.add_argument("--fps", type=float, default=1.0)
    parser.add_argument("--videos", nargs="*")
    args = parser.parse_args()
    model = QuestionVLM(args.model)
    for path in videos():
        if args.videos and path.stem not in args.videos:
            continue
        target = CACHE / "probes" / args.name / f"{path.stem}.json"
        if target.exists():
            continue
        scene = Scene.from_json(json.loads((CACHE / "scene" / f"{path.stem}.json").read_text(encoding="utf-8")))
        pose = PoseSequence.from_json(json.loads((CACHE / "pose" / f"{path.stem}.json").read_text(encoding="utf-8")))
        began = time.perf_counter()
        video = decode(path, args.fps)
        series = {probe.key: {"times": [], "values": []} for probe in HAND_PROBES}
        boxes = []
        for moment in video.times:
            people = pose.people[int(np.argmin(np.abs(pose.times - moment)))]
            box = hand_box(people, scene)
            if box is None:
                # No hands over the desk: nothing is being held there.
                answers = [0.0] * len(HAND_PROBES)
            else:
                answers = model.probe(crop(video.frame_at(moment), box), [p.question for p in HAND_PROBES],
                                      CONTEXT, HAND_TOKENS)
            boxes.append(box)
            for probe, value in zip(HAND_PROBES, answers, strict=True):
                series[probe.key]["times"].append(float(moment))
                series[probe.key]["values"].append(float(value))
        write_json(target, {"video": path.name, "model": model.name, "duration": video.duration, "series": series,
                            "boxes": boxes, "seconds": time.perf_counter() - began})
        print(f"{args.name} {path.name}: {len(video.times)} frames in {time.perf_counter() - began:.1f}s", flush=True)


if __name__ == "__main__":
    main()

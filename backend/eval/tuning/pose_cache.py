"""Cache Keypoint R-CNN people and skeletons for every video."""
import argparse
import json
import time

from backend.perception.pose import PoseEstimator, detect_people
from common import CACHE, videos, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=float, default=4.0)
    parser.add_argument("--device")
    parser.add_argument("--videos", nargs="*")
    args = parser.parse_args()
    out = CACHE / "pose"
    estimator = PoseEstimator(args.device)
    for path in videos():
        if args.videos and path.stem not in args.videos:
            continue
        target = out / f"{path.stem}.json"
        if target.exists():
            continue
        began = time.perf_counter()
        sequence = detect_people(path, estimator, args.fps)
        write_json(target, sequence.to_json() | {"fps": args.fps})
        print(f"pose {path.name}: {len(sequence.times)} samples, "
              f"{sum(map(len, sequence.people)) / max(1, len(sequence.people)):.2f} people/frame, "
              f"{time.perf_counter() - began:.1f}s", flush=True)


if __name__ == "__main__":
    main()

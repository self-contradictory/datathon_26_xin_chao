"""Cache the grounded scene layout (desk, safe, laptop, door) for every video."""
import argparse
import time

from backend.perception.scene import locate
from backend.reconstruction.vlm import QuestionVLM
from common import CACHE, videos, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="2b")
    parser.add_argument("--videos", nargs="*")
    args = parser.parse_args()
    model = QuestionVLM(args.model)
    for path in videos():
        if args.videos and path.stem not in args.videos:
            continue
        target = CACHE / "scene" / f"{path.stem}.json"
        if target.exists():
            continue
        began = time.perf_counter()
        scene = locate(model, path)
        write_json(target, scene.to_json())
        missing = [key for key, ok in scene.grounded.items() if not ok]
        print(f"scene {path.name}: {time.perf_counter() - began:.1f}s, fallback for {missing or 'none'}", flush=True)


if __name__ == "__main__":
    main()

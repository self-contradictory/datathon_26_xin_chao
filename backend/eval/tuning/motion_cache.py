"""Cache local patch motion (frame difference, DIS flow, background difference) for every video."""
import argparse
import time

from backend.perception.motion import patch_motion
from common import CACHE, videos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--videos", nargs="*")
    args = parser.parse_args()
    out = CACHE / "motion"
    out.mkdir(parents=True, exist_ok=True)
    for path in videos():
        if args.videos and path.stem not in args.videos:
            continue
        target = out / f"{path.stem}.npz"
        if target.exists():
            continue
        began = time.perf_counter()
        motion = patch_motion(path, args.fps)
        motion.save(target)
        print(f"motion {path.name}: {len(motion.times)} samples, grid {motion.grid}, "
              f"{time.perf_counter() - began:.1f}s", flush=True)


if __name__ == "__main__":
    main()

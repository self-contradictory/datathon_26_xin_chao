"""Cache zoomed region probe probabilities (desk, hands, safe, laptop, door) for every video.

Each region is sampled at its own rate (regions.RATES); every key keeps its own timestamps.
"""
import argparse
import json
import time

from backend.perception.regions import CONTEXT, RATES, REGION_PROBES, TOKENS, crop
from backend.perception.scene import Scene
from backend.reconstruction.video import decode
from backend.reconstruction.vlm import QuestionVLM
from common import CACHE, videos, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="regions")
    parser.add_argument("--model", default="2b")
    parser.add_argument("--regions", nargs="*", default=list(REGION_PROBES))
    parser.add_argument("--keys", nargs="*", help="only these probe keys")
    parser.add_argument("--rate", type=float, help="override every region's sample rate")
    parser.add_argument("--videos", nargs="*")
    args = parser.parse_args()
    probes_by_region = {region: tuple(p for p in REGION_PROBES[region] if not args.keys or p.key in args.keys)
                        for region in args.regions}
    args.regions = [region for region, probes in probes_by_region.items() if probes]
    rates = {region: args.rate or RATES[region] for region in args.regions}
    model = QuestionVLM(args.model)
    out = CACHE / "probes" / args.name
    fps = max(rates.values())
    for path in videos():
        if args.videos and path.stem not in args.videos:
            continue
        target = out / f"{path.stem}.json"
        if target.exists():
            continue
        scene = Scene.from_json(json.loads((CACHE / "scene" / f"{path.stem}.json").read_text(encoding="utf-8")))
        boxes = scene.regions
        began = time.perf_counter()
        video = decode(path, fps)
        series = {probe.key: {"times": [], "values": []}
                  for region in args.regions for probe in probes_by_region[region]}
        due = {region: 0.0 for region in args.regions}
        for moment in video.times:
            frame = video.frame_at(moment)
            for region in args.regions:
                if moment + 1e-6 < due[region]:
                    continue
                due[region] = moment + 1.0 / rates[region] - 0.5 / fps
                probes = probes_by_region[region]
                answers = model.probe(crop(frame, boxes[region]), [p.question for p in probes], CONTEXT,
                                      TOKENS[region])
                for probe, value in zip(probes, answers, strict=True):
                    series[probe.key]["times"].append(float(moment))
                    series[probe.key]["values"].append(value)
        write_json(target, {
            "video": path.name, "model": model.name, "regions": args.regions, "rates": rates, "tokens": TOKENS,
            "boxes": boxes, "duration": video.duration, "series": series,
            "seconds": time.perf_counter() - began,
        })
        print(f"{args.name} {path.name}: {len(video.times)} frames in {time.perf_counter() - began:.1f}s", flush=True)


if __name__ == "__main__":
    main()

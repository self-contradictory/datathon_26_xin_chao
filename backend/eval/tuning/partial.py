"""Score the current perception configuration on the videos whose region probes are cached."""
import sys

from backend.perception.features import FeatureConfig
from backend.perception.fusion import FusionConfig
from backend.perception.pipeline import PerceptionConfig
from bench import judge
from calibrate import thresholds
from common import CACHE, expected, metrics, score_video
from fused_bench import Experiment, build


def config(**fusion):
    return PerceptionConfig(use_regions=True, use_cv=True, features=FeatureConfig(safe_reach=0.15),
                            fusion=FusionConfig(base_bias=thresholds("base-full"), region_bias=thresholds("regions"),
                                                **fusion))


def main(cfg, verbose=True):
    done = {p.stem for p in (CACHE / "probes" / "regions").glob("*.json")}
    rows = []
    for video in expected():
        stem = video.rsplit(".", 1)[0]
        if stem not in done:
            continue
        findings, _ = judge(build(Experiment("partial", "base-full", "regions", cfg), stem))
        row = score_video(video, findings)
        rows.append(row)
        if verbose:
            error = "" if row["time_error"] is None else f" dt={row['time_error']:.1f}"
            print(("ok " if row["correct"] else "BAD"), f"{stem:6s}", f"{row['expected']:13s}", ", ".join(r.split("-")[0] for r in row["rules"]) or "-", error)
    m = metrics(rows)
    print(f"{m['correct']}/{m['videos']} TP {m['tp']} TN {m['tn']} FP {m['fp']} FN {m['fn']} aspect recall {m['aspect_recall']:.2f}")
    return rows


if __name__ == "__main__":
    main(config())

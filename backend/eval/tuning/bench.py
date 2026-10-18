"""Score cached probe runs offline: timeline decode, rule engine, verdicts and timestamps.

Example:
    .venv/bin/python -B eval/tuning/bench.py base-full
"""
import argparse
import json
from pathlib import Path

import numpy as np

from backend.reconstruction.decode import Observation
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, decode_tracks
from backend.reconstruction.probes import PROBES
from backend.reconstruction.video import DecodedVideo
from backend.rules.engine import evaluate
from backend.rules.registry import load_registry
from backend.rules.verdict import ReportingPolicy, reportable
from common import CACHE, VIDEOS, expected, metrics, score_video, write_json
from timeline_eval import ANNOTATIONS, score as score_timeline

REGISTRY = load_registry()
ORIGINAL = load_registry(Path(__file__).with_name("cashdesk_original.yaml"))
POLICY = ReportingPolicy(production_only=False)


def reconstruction(cache: dict, probabilities: dict[str, list[float]] | None = None,
                   probes=PROBES) -> Reconstruction:
    times = np.asarray(cache["times"])
    video = DecodedVideo(VIDEOS / cache["video"], cache["duration"], cache["native_fps"], cache["width"],
                         cache["height"], cache["fps"], times, cache["frame_indices"], [])
    values = probabilities or cache["probabilities"]
    tracks = {probe.key: AttributeTrack(probe, [Observation(float(t), float(p))
                                                for t, p in zip(times, values[probe.key], strict=True)])
              for probe in probes}
    decode_tracks(video, tracks)
    return Reconstruction(video, tracks, cache["model"])


def judge(recon: Reconstruction, registry=None) -> tuple[list[dict], object]:
    graph = build_timeline(recon)
    report = evaluate(registry or REGISTRY, graph, "shadow")
    findings = [{"rule_id": f.rule_id, "outcome": f.outcome, "kind": f.unknown_kind,
                 "timecode_sec": f.timecode_sec, "reason": f.reason}
                for f in reportable(report, POLICY)]
    return findings, graph


def run(name: str, verbose: bool = True, registry=None, label: str | None = None) -> dict:
    rows, decoded, durations = [], {}, {}
    for video in expected():
        path = CACHE / "probes" / name / f"{Path(video).stem}.json"
        if not path.exists():
            continue
        cache = json.loads(path.read_text(encoding="utf-8"))
        recon = reconstruction(cache)
        findings, _ = judge(recon, registry)
        stem = Path(video).stem
        if stem in ANNOTATIONS:
            decoded[stem] = {key: [(s.start, s.end, s.value) for s in track.segments]
                             for key, track in recon.tracks.items()}
            durations[stem] = recon.video.duration
        row = score_video(video, findings)
        row["findings"] = findings
        rows.append(row)
    summary = {"name": label or name, "metrics": metrics(rows), "timeline": score_timeline(decoded, durations),
               "rows": rows}
    write_json(CACHE / "results" / f"{label or name}.json", summary)
    if verbose:
        report(summary)
    return summary


def report(summary: dict) -> None:
    m = summary["metrics"]
    print(f"{summary['name']}: {m['correct']}/{m['videos']} correct, TP {m['tp']} TN {m['tn']} FP {m['fp']} "
          f"FN {m['fn']}, F1 {m['f1'] or 0:.3f}, aspect recall {m['aspect_recall'] or 0:.2f}, "
          f"time hits <=3s {m['time_hits_3s']} <=5s {m['time_hits_5s']}")
    timeline = summary["timeline"]
    print("  timeline balanced accuracy: mean", timeline["_mean_balanced_accuracy"], "|",
          ", ".join(f"{k} {v['balanced_accuracy']}" for k, v in timeline.items() if not k.startswith("_")))
    for row in summary["rows"]:
        mark = "ok " if row["correct"] else "BAD"
        error = f" dt={row['time_error']:.1f}s" if row["time_error"] is not None else ""
        print(f"  {mark} {row['video']:<10} {row['expected']:<13} {', '.join(row['rules']) or '-'}{error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--original-rules", action="store_true")
    args = parser.parse_args()
    run(args.name, registry=ORIGINAL if args.original_rules else None,
        label=f"{args.name}-original-rules" if args.original_rules else None)

"""Score compare_windows.py outputs against the timeline annotations and the violation labels.

Usage: .venv/bin/python -B eval/score_windows.py [var/compare_windows]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from backend.rules.registry import load_registry

EVAL = Path(__file__).resolve().parent
GRID = 0.1
KNOWN = 0.6
TIME_TOLERANCE = 3.0


def _mask(intervals, times: np.ndarray) -> np.ndarray:
    result = np.zeros(len(times), bool)
    for start, end in intervals:
        result |= (times >= start) & (times <= end)
    return result


def timeline_rows(tracks: dict, annotation: dict, duration: float) -> list[dict]:
    times = np.arange(0.0, duration, GRID)
    rows = []
    for key, truth in annotation["attributes"].items():
        keep = ~_mask(annotation.get("ignore", {}).get(key, []), times)
        predicted = [(s["start"], s["end"]) for s in tracks[key]["segments"] if s["value"] and s["confidence"] >= KNOWN]
        p, t = _mask(predicted, times)[keep], _mask(truth, times)[keep]
        tp, fp, fn = int((p & t).sum()), int((p & ~t).sum()), int((~p & t).sum())
        rows.append({"attribute": key, "accuracy": float((p == t).mean()),
                     "iou": tp / (tp + fp + fn) if t.any() else None,
                     "false_alarm": bool(p.any()) if not t.any() else None})
    return rows


def rule_row(report: dict, label: float | None, expected: set[str]) -> dict:
    findings = [f for rule in report["rules"] for f in rule["findings"]]
    violations = [f for f in findings if f["outcome"] == "VIOLATION"]
    hits = [] if label is None else [
        f for f in violations if f["rule_id"] in expected
        and (abs(f["timecode_sec"] - label) <= TIME_TOLERANCE
             or f["start_sec"] - TIME_TOLERANCE <= label <= f["end_sec"] + TIME_TOLERANCE)]
    return {"labelled": label is not None, "detected": bool(hits), "false_positives": len(violations) - len(hits),
            "verdict_correct": bool(violations) == (label is not None) and (label is None or bool(hits)),
            "violations": [f"{f['rule_id'].split('-')[0]}@{f['timecode_sec']:.1f}" for f in violations],
            "unknown": sorted({f"{f['rule_id'].split('-')[0]}:{f['unknown_kind']}" for f in findings
                               if f["outcome"] == "UNKNOWN"})}


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else EVAL.parent / "var" / "compare_windows"
    annotations = json.loads((EVAL / "reconstruction_annotations.json").read_text())
    labels = json.loads((EVAL / "violation_times.json").read_text())
    examples = defaultdict(set)
    for rule in load_registry().rules:
        for video in rule.dataset_examples:
            examples[video].add(rule.rule_id)
    summary = defaultdict(lambda: {"timeline": [], "rules": [], "seconds": [], "windows": 0, "failures": 0})
    detail = []
    for run_file in sorted(root.glob("*/*/*/run.json")):
        directory = run_file.parent
        run = json.loads(run_file.read_text())
        model, video, approach = directory.parts[-3:]
        graph = json.loads((directory / "steg.json").read_text())
        rows = timeline_rows(json.loads((directory / "tracks.json").read_text()), annotations[video],
                             graph["video"]["duration_sec"])
        rule = rule_row(json.loads((directory / "report.json").read_text()), labels[video], examples[video])
        entry = summary[(model, approach)]
        entry["timeline"] += rows
        entry["rules"].append(rule)
        entry["seconds"].append(run["total_seconds"])
        entry["windows"] += run.get("windows", 0)
        entry["failures"] += run.get("parse_failures", 0)
        detail.append({"model": model, "video": video, "approach": approach, "rule": rule,
                       "timeline": rows, "seconds": run["total_seconds"],
                       "semantic_calls": run["semantic_calls"], "semantic_errors": run["semantic_errors"]})
    print("| model | approach | attr accuracy | positive IoU | false alarms | violation found | false positives | verdicts | s/video | JSON failures |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    table = []
    for (model, approach), entry in sorted(summary.items()):
        rows, rules = entry["timeline"], entry["rules"]
        ious = [row["iou"] for row in rows if row["iou"] is not None]
        alarms = [row["false_alarm"] for row in rows if row["false_alarm"] is not None]
        positives = [rule for rule in rules if rule["labelled"]]
        line = {"model": model, "approach": approach,
                "accuracy": float(np.mean([row["accuracy"] for row in rows])),
                "positive_iou": float(np.mean(ious)) if ious else None,
                "false_alarms": f"{sum(alarms)}/{len(alarms)}",
                "detected": f"{sum(rule['detected'] for rule in positives)}/{len(positives)}",
                "false_positives": sum(rule["false_positives"] for rule in rules),
                "verdicts": f"{sum(rule['verdict_correct'] for rule in rules)}/{len(rules)}",
                "seconds": float(np.mean(entry["seconds"])),
                "json_failures": f"{entry['failures']}/{entry['windows']}" if entry["windows"] else "-"}
        table.append(line)
        print(f"| {model} | {approach} | {line['accuracy']:.3f} | {line['positive_iou']:.3f} | {line['false_alarms']} | "
              f"{line['detected']} | {line['false_positives']} | {line['verdicts']} | {line['seconds']:.0f} | {line['json_failures']} |")
    print()
    for item in detail:
        attributes = ", ".join(f"{row['attribute']}={row['accuracy']:.2f}" for row in item["timeline"])
        print(f"{item['model']} {item['video']} {item['approach']}: violations={item['rule']['violations']} "
              f"unknown={item['rule']['unknown']}\n    {attributes}")
    (root / "summary.json").write_text(json.dumps({"table": table, "detail": detail}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

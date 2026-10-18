"""Metrics for paired semantic experiments; labels never enter the analyzer."""
import statistics

import numpy as np

from backend.reconstruction.graph import CLAIMS


def score_timeline(graph, annotations):
    entry = annotations.get(graph.video.id)
    if entry is None:
        return {}
    times = np.arange(0, graph.video.duration_sec, 0.25)
    result = {}
    for key, spans in entry["attributes"].items():
        entity, prop, yes, no = CLAIMS[key]
        truth = np.array([any(a <= t <= b for a, b in spans) for t in times])
        valid = np.array([not any(a <= t <= b for a, b in entry.get("ignore", {}).get(key, [])) for t in times])
        predicted = np.full(len(times), -1, dtype=int)
        for track in graph.state_tracks:
            if track.entity_id != entity or track.property != prop:
                continue
            for span in track.intervals:
                chosen = (times >= span.start_sec) & (times <= span.end_sec)
                value = 1 if span.value == yes else 0 if span.value == no else -1
                predicted[chosen] = value if span.knowledge == "bounded_by_observations" else -1
        # Abstentions are scored as errors, not silently treated as correct negatives.
        result[key] = {"tp": int(np.sum(valid & truth & (predicted == 1))),
                       "tn": int(np.sum(valid & ~truth & (predicted == 0))),
                       "fp": int(np.sum(valid & ~truth & (predicted != 0))),
                       "fn": int(np.sum(valid & truth & (predicted != 1))),
                       "unknown": int(np.sum(valid & (predicted == -1))), "samples": int(valid.sum())}
    return result


def aggregate(rows):
    successful = [r for r in rows if r["status"] == "done"]
    tp = sum(r["expected"] == r["predicted"] == "violation" for r in successful)
    tn = sum(r["expected"] == r["predicted"] == "no_violation" for r in successful)
    fp = sum(r["expected"] == "no_violation" and r["predicted"] == "violation" for r in successful)
    fn = sum(r["expected"] == "violation" and r["predicted"] == "no_violation" for r in successful)
    pooled = {}
    for row in successful:
        for key, counts in row.get("timeline", {}).items():
            target = pooled.setdefault(key, dict.fromkeys(counts, 0))
            for name, value in counts.items():
                target[name] += value
    f1s = [2*v["tp"]/(2*v["tp"]+v["fp"]+v["fn"]) for v in pooled.values() if 2*v["tp"]+v["fp"]+v["fn"]]
    unknown = sum(v["unknown"] for v in pooled.values())
    samples = sum(v["samples"] for v in pooled.values())
    aspects = sum(r.get("aspects_total", 0) for r in successful)
    aspect_hits = sum(r.get("aspects_hit", 0) for r in successful)
    errors = [r["time_error"] for r in successful if r["expected"] == r["predicted"] == "violation"
              and r.get("time_error") is not None]
    return {"attempted": len(rows), "completed": len(successful), "failed": len(rows)-len(successful),
            "correct": tp+tn, "accuracy": (tp+tn)/len(rows) if rows else None,
            "accuracy_completed": (tp+tn)/len(successful) if successful else None,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "precision": tp/(tp+fp) if tp+fp else None, "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            "aspect_recall": aspect_hits/aspects if aspects else None,
            "median_time_error": statistics.median(errors) if errors else None,
            "time_scored": len(errors), "time_hits_3s": sum(e <= 3 for e in errors),
            "timeline_macro_f1": statistics.mean(f1s) if f1s else None,
            "timeline_known_coverage": 1-unknown/samples if samples else None,
            "timeline_videos": sum(bool(r.get("timeline")) for r in successful), "timeline_counts": pooled,
            "seconds": sum(r.get("seconds", 0) for r in rows),
            "model_calls": sum(r.get("model_calls", 0) for r in rows),
            "model_cache_hits": sum(r.get("model_cache_hits", 0) for r in rows),
            "followup_errors": sum(r.get("followup_errors", 0) for r in rows)}

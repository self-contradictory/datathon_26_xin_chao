"""Frame-level timeline accuracy against eval/reconstruction_annotations.json.

Each annotated attribute is sampled every 0.25 s; ignore spans are skipped. Reports balanced
accuracy and F1 of the decoded binary state per attribute, pooled over videos.
"""
import json

import numpy as np

from common import EVAL

ANNOTATIONS = {key: value for key, value in
               json.loads((EVAL / "reconstruction_annotations.json").read_text(encoding="utf-8")).items()
               if not key.startswith("_")}


def _covered(moment: float, spans: list[list[float]]) -> bool:
    return any(start - 1e-6 <= moment <= end + 1e-6 for start, end in spans)


def truth(video: str, key: str, times: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    entry = ANNOTATIONS.get(video)
    if entry is None or key not in entry["attributes"]:
        return None
    spans = entry["attributes"][key]
    ignore = entry.get("ignore", {}).get(key, [])
    labels = np.array([_covered(t, spans) for t in times])
    valid = np.array([not _covered(t, ignore) for t in times])
    return labels, valid


def state_at(segments: list[tuple[float, float, bool]], times: np.ndarray) -> np.ndarray:
    out = np.zeros(len(times), bool)
    for start, end, value in segments:
        out[(times >= start - 1e-6) & (times <= end + 1e-6)] = value
    return out


def score(decoded: dict[str, dict[str, list[tuple[float, float, bool]]]], durations: dict[str, float]) -> dict:
    """decoded: video stem -> key -> [(start, end, value)]."""
    pooled: dict[str, np.ndarray] = {}
    for video, tracks in decoded.items():
        times = np.arange(0.0, durations[video], 0.25)
        for key, segments in tracks.items():
            answer = truth(video, key, times)
            if answer is None:
                continue
            labels, valid = answer
            predicted = state_at(segments, times)
            counts = np.array([
                np.sum(valid & labels & predicted), np.sum(valid & ~labels & ~predicted),
                np.sum(valid & ~labels & predicted), np.sum(valid & labels & ~predicted),
            ])
            pooled[key] = pooled.get(key, np.zeros(4, int)) + counts
    result = {}
    for key, (tp, tn, fp, fn) in sorted(pooled.items()):
        tpr = tp / (tp + fn) if tp + fn else None
        tnr = tn / (tn + fp) if tn + fp else None
        balanced = np.mean([v for v in (tpr, tnr) if v is not None])
        result[key] = {"balanced_accuracy": round(float(balanced), 3),
                       "f1": round(2 * tp / (2 * tp + fp + fn), 3) if 2 * tp + fp + fn else None,
                       "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)}
    scored = [v["balanced_accuracy"] for v in result.values()]
    result["_mean_balanced_accuracy"] = round(float(np.mean(scored)), 3) if scored else None
    return result

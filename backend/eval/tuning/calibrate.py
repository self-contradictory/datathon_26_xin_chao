"""Label-free per-question calibration: Otsu threshold on the pooled logit histogram of every frame."""
import json
import sys

import numpy as np

from backend.perception.hands import hand_evidence
from common import CACHE, write_json


def otsu(values: np.ndarray, bins: int = 64) -> tuple[float, float]:
    """Returns the threshold and the between-class share of variance (1.0 = perfectly bimodal)."""
    hist, edges = np.histogram(values, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    weight = hist.cumsum()
    mean = (hist * centres).cumsum()
    total, grand = weight[-1], mean[-1]
    between = np.zeros(len(hist))
    for i in range(len(hist) - 1):
        w0, w1 = weight[i], total - weight[i]
        if w0 == 0 or w1 == 0:
            continue
        m0, m1 = mean[i] / w0, (grand - mean[i]) / w1
        between[i] = w0 * w1 * (m0 - m1) ** 2
    best = int(np.argmax(between))
    return float(edges[best + 1]), float(between[best] / (total ** 2 * values.var())) if values.var() > 0 else 0.0


def pooled_logits(name: str) -> dict[str, np.ndarray]:
    """Every frame's score per question, leaving out frames a pass skipped (no hands found)."""
    pooled: dict[str, list[float]] = {}
    for path in sorted((CACHE / "probes" / name).glob("*.json")):
        data = json.loads(path.read_text())
        if "series" in data:
            series = hand_evidence({k: (np.asarray(v["times"]), np.asarray(v["values"]))
                                    for k, v in data["series"].items()})
            series = {k: values for k, (_, values) in series.items()}
        else:
            series = data["probabilities"]
        probed = [box is not None for box in data["boxes"]] if isinstance(data.get("boxes"), list) else None
        for key, values in series.items():
            pooled.setdefault(key, []).extend(v for i, v in enumerate(values) if probed is None or probed[i])
    return {k: np.log(np.clip(v, 1e-4, 1 - 1e-4) / (1 - np.clip(v, 1e-4, 1 - 1e-4))) for k, v in
            ((k, np.asarray(v)) for k, v in pooled.items())}


def thresholds(name: str, min_separation: float = 0.6) -> dict[str, float]:
    """Otsu thresholds for clearly bimodal questions; others keep the model's own 0.5 point.
    Layered cache names ("regions+regions2") take each key from the last cache that has it."""
    result = {}
    for layer in name.split("+"):
        part, _, keep = layer.partition("[")
        keep = set(keep.rstrip("]").split(",")) if keep else None
        for key, values in pooled_logits(part).items():
            if keep is not None and key not in keep:
                continue
            threshold, separation = otsu(values)
            result[key] = round(threshold, 2) if separation >= min_separation else 0.0
    return result


if __name__ == "__main__":
    name = sys.argv[1]
    result = thresholds(name)
    write_json(CACHE / "calibration" / f"{name}.json", result)
    for key, values in sorted(pooled_logits(name).items()):
        threshold, separation = otsu(values)
        print(f"{key:20s} otsu {threshold:+.2f} separation {separation:.2f} -> used {result[key]:+.2f}")

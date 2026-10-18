"""Frame-level AUC and best threshold of cached probe scores against the timeline annotations."""
import json
import sys

import numpy as np

from common import CACHE
from timeline_eval import ANNOTATIONS, truth


def auc(scores, labels):
    order = np.argsort(scores)
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    pos = labels.sum()
    neg = len(labels) - pos
    return (ranks[labels].sum() - pos * (pos + 1) / 2) / (pos * neg) if pos and neg else float("nan")


def collect(name):
    pooled = {}
    for stem in ANNOTATIONS:
        path = CACHE / "probes" / name / f"{stem}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        series = ({k: (np.asarray(v["times"]), np.asarray(v["values"])) for k, v in data["series"].items()}
                  if "series" in data else
                  {k: (np.asarray(data["times"]), np.asarray(v)) for k, v in data["probabilities"].items()})
        for key, (times, values) in series.items():
            answer = truth(stem, key, times)
            if answer is None:
                continue
            labels, valid = answer
            pooled.setdefault(key, ([], []))
            pooled[key][0].extend(values[valid])
            pooled[key][1].extend(labels[valid])
    return pooled


if __name__ == "__main__":
    for key, (scores, labels) in sorted(collect(sys.argv[1]).items()):
        scores, labels = np.asarray(scores), np.asarray(labels, bool)
        logits = np.log(np.clip(scores, 1e-4, 1 - 1e-4) / (1 - np.clip(scores, 1e-4, 1 - 1e-4)))
        best = max(np.unique(np.round(logits, 1)), key=lambda t: (
            np.mean((logits >= t)[labels]) + np.mean((logits < t)[~labels])) if labels.any() and (~labels).any() else 0)
        print(f"{key:20s} n={len(labels):4d} pos={labels.sum():4d} AUC={auc(scores, labels):.3f} "
              f"best logit threshold={best:+.1f} mean p(pos)={scores[labels].mean() if labels.any() else float('nan'):.2f} "
              f"mean p(neg)={scores[~labels].mean() if (~labels).any() else float('nan'):.2f}")

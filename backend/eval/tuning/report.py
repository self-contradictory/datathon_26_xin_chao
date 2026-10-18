"""Print a comparison table of saved tuning results (var/tuning/results/*.json)."""
import json
import sys

from common import CACHE


def row(name: str) -> str:
    data = json.loads((CACHE / "results" / f"{name}.json").read_text(encoding="utf-8"))
    m, t = data["metrics"], data["timeline"]
    acc = f"{m['correct']}/{m['videos']} ({m['accuracy']:.0%})"
    f1 = f"{m['f1']:.2f}" if m["f1"] is not None else "-"
    recall = f"{m['aspect_recall']:.2f}" if m["aspect_recall"] is not None else "-"
    median = f"{m['median_time_error']:.1f}" if m["median_time_error"] is not None else "-"
    return (f"| {name} | {acc} | {m['tp']} | {m['tn']} | {m['fp']} | {m['fn']} | {f1} | {recall} | "
            f"{m['time_hits_3s']}/{m['tp']} | {median} | {t['_mean_balanced_accuracy']} |")


if __name__ == "__main__":
    print("| run | verdict accuracy | TP | TN | FP | FN | F1 | aspect recall | dt<=3s | median dt | timeline bal. acc |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name in sys.argv[1:]:
        print(row(name))

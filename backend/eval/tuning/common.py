"""Shared paths, labels and metrics for the offline tuning scripts.

Labels are read only here, by the scorers. The analyzers never receive them.
"""
import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
EVAL = BACKEND / "eval"
VIDEOS = BACKEND.parent / "data" / "open" / "videos"
CACHE = BACKEND / "var" / "tuning"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def videos() -> list[Path]:
    return sorted(VIDEOS.glob("*.mov"), key=lambda path: int(path.stem.split("-")[-1]))


def expected() -> dict[str, str]:
    return json.loads((EVAL / "expected_api_verdicts.json").read_text(encoding="utf-8"))


def label_times() -> dict[str, float | None]:
    times = json.loads((EVAL / "violation_times.json").read_text(encoding="utf-8"))
    return {key: value for key, value in times.items() if not key.startswith("_")}


def aspects() -> dict[str, list[dict]]:
    catalog = json.loads((EVAL / "dataset_labels.json").read_text(encoding="utf-8"))
    return {item["video"]: item["aspects"] for item in catalog["videos"]}


def metrics(rows: list[dict]) -> dict:
    tp = sum(r["expected"] == "violation" and r["predicted"] == "violation" for r in rows)
    tn = sum(r["expected"] == "no_violation" and r["predicted"] == "no_violation" for r in rows)
    fp = sum(r["expected"] == "no_violation" and r["predicted"] == "violation" for r in rows)
    fn = sum(r["expected"] == "violation" and r["predicted"] == "no_violation" for r in rows)
    hits = [r for r in rows if r["expected"] == "violation" and r["predicted"] == "violation"]
    errors = [r["time_error"] for r in hits if r.get("time_error") is not None]
    aspect_total = sum(r.get("aspects_total", 0) for r in rows)
    aspect_hit = sum(r.get("aspects_hit", 0) for r in rows)
    return {
        "videos": len(rows), "correct": tp + tn, "accuracy": (tp + tn) / len(rows) if rows else None,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "time_hits_3s": sum(e <= 3 for e in errors), "time_hits_5s": sum(e <= 5 for e in errors),
        "median_time_error": sorted(errors)[len(errors) // 2] if errors else None,
        "aspect_recall": aspect_hit / aspect_total if aspect_total else None,
    }


def score_video(name: str, findings: list[dict]) -> dict:
    """findings: reportable findings as dicts with rule_id and timecode_sec."""
    stem = Path(name).stem
    truth = expected()[name]
    moment = label_times().get(stem)
    rule_ids = {f["rule_id"] for f in findings}
    visual = [a for a in aspects().get(name, []) if a["observability"] != "external_only"]
    row = {
        "video": name, "expected": truth,
        "predicted": "violation" if findings else "no_violation",
        "rules": sorted(rule_ids),
        "aspects_total": len(visual),
        "aspects_hit": sum(bool(rule_ids & set(a["any_of_rules"])) for a in visual),
        "time_error": None,
    }
    if moment is not None and findings:
        relevant = [f for f in findings if any(f["rule_id"] in a["any_of_rules"] for a in visual)] or findings
        row["time_error"] = min(abs(f["timecode_sec"] - moment) for f in relevant)
    row["correct"] = row["predicted"] == truth
    return row

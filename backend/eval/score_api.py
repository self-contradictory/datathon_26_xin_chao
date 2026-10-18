"""Score API result JSON files against the frozen dataset labels, without inference."""
import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_EXPECTED = HERE / "expected_api_verdicts.json"
DEFAULT_RESULTS = HERE.parent / "var" / "dataset-verdicts"
VERDICTS = {"violation", "no_violation"}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_expected(path: Path = DEFAULT_EXPECTED) -> dict[str, str]:
    expected = json.loads(path.read_text(encoding="utf-8-sig"))
    if not expected or any(value not in VERDICTS for value in expected.values()):
        raise ValueError("Expected a nonempty filename-to-verdict mapping")
    return expected


def score(results: Path, expected: dict[str, str], catalog_path: Path = HERE / "dataset_labels.json") -> dict:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    video_labels = {item["video"]: item for item in catalog.get("videos", [])}
    # Rule names are read only by the scorer, never passed to the inference API.
    from backend.rules.registry import load_registry

    names = {rule.name: rule.rule_id for rule in load_registry().rules}
    rows = []
    for name, truth in expected.items():
        path = results / f"{name}.json"
        response = {"status": "missing"}
        if path.exists():
            try:
                response = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(response, dict):
                    raise ValueError("API result must be a JSON object")
            except (ValueError, OSError) as error:
                response = {"status": "invalid", "error": str(error)}
        status = response.get("status", "invalid")
        if status not in {"done", "processing", "failed", "missing", "invalid", "client_error"}:
            status = "invalid"
        predicted = response.get("verdict") if status == "done" else None
        if status == "done" and predicted not in VERDICTS:
            status, predicted = "invalid", None
        violations = response.get("violations") or []
        rule_ids = {names[item.get("type")] for item in violations if item.get("type") in names}
        aspects = [aspect for aspect in video_labels.get(name, {}).get("aspects", [])
                   if aspect["observability"] != "external_only"]
        matched = sum(bool(rule_ids.intersection(aspect["any_of_rules"])) for aspect in aspects)
        rows.append({
            "video": name, "expected": truth, "predicted": predicted,
            "correct": status == "done" and predicted == truth, "status": status,
            "violations": len(violations), "job_id": response.get("job_id"),
            "expected_visual_aspects": len(aspects), "matched_visual_aspects": matched,
            "reported_rule_ids": sorted(rule_ids), "error": response.get("error"),
        })
    completed = [row for row in rows if row["status"] == "done"]
    tp = sum(row["expected"] == row["predicted"] == "violation" for row in completed)
    tn = sum(row["expected"] == row["predicted"] == "no_violation" for row in completed)
    fp = sum(row["expected"] == "no_violation" and row["predicted"] == "violation" for row in completed)
    fn = sum(row["expected"] == "violation" and row["predicted"] == "no_violation" for row in completed)
    required = sum(row["expected_visual_aspects"] for row in completed)
    matched = sum(row["matched_visual_aspects"] for row in completed)
    summary = {
        "planned": len(rows), "completed": len(completed),
        "failed": sum(row["status"] in {"failed", "client_error", "invalid"} for row in rows),
        "remaining": sum(row["status"] in {"missing", "processing"} for row in rows),
        "correct": tp + tn, "accuracy": (tp + tn) / len(completed) if completed else None,
        "correct_over_all": (tp + tn) / len(rows),
        "true_positives": tp, "true_negatives": tn, "false_positives": fp, "false_negatives": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "labelled_visual_aspect_recall": matched / required if required else None,
        "mismatches": [row["video"] for row in completed if not row["correct"]],
        "note": "Dataset agreement, not independently validated legal compliance. "
                "API verdicts include reportable possible violations. Labels are used only for scoring. "
                "Failed or incomplete jobs have no predicted verdict. Aspect recall measures reported "
                "rule coverage, not temporal accuracy or confirmation; external-only accounting is excluded.",
        "results": rows,
    }
    results.mkdir(parents=True, exist_ok=True)
    write_json(results / "summary.json", summary)
    fields = ["video", "expected", "predicted", "correct", "status", "violations", "job_id",
              "expected_visual_aspects", "matched_visual_aspects", "reported_rule_ids", "error"]
    with (results / "verdicts.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    accuracy = f"{summary['accuracy']:.1%}" if completed else "n/a"
    print(f"Completed {len(completed)}/{len(rows)}; accuracy {accuracy}; "
          f"TP={tp} TN={tn} FP={fp} FN={fn}; failed={summary['failed']} remaining={summary['remaining']}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="?", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    args = parser.parse_args()
    summary = score(args.results, load_expected(args.expected))
    print("Mismatches:", ", ".join(summary["mismatches"]) or "none among completed videos")
    print("Results:", args.results.resolve())


if __name__ == "__main__":
    main()

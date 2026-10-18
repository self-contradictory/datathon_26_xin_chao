"""Compare cached/fresh 2B perception, JSON follow-ups, and plain-text video descriptions.

Run from any directory with the backend's .venv Python. Default: every labelled video, six
methods, frozen source, resumable calls, live score tables and JSON/CSV/Markdown reports.
"""
import argparse
import csv
import gc
import hashlib
import json
import logging
import re
import shutil
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
METHODS = ("baseline", "structured_followups", "plain_followups", "captions_only",
           "baseline_captions", "captions_followups")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    # Windows' locale encoding can turn UTF-8 Cyrillic Х into the two characters РҐ.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def video_key(name):
    stem = Path(name).stem.casefold().replace("х", "x")
    match = re.fullmatch(r"x[-_ ]*0*(\d+)", stem)
    return ("x", int(match[1])) if match else (stem,)


def resolve_videos(directory, labels):
    if not directory.is_dir():
        raise ValueError(f"Video directory not found: {directory}. Set --videos-dir to the folder containing your videos.")
    candidates = [p for p in directory.iterdir() if p.is_file() and p.suffix.casefold() in {".mov", ".mp4", ".m4v", ".mkv"}]
    resolved, missing = {}, []
    for name in labels:
        exact = directory / name
        if exact.is_file():
            resolved[name] = exact
            continue
        matches = [p for p in candidates if video_key(p.name) == video_key(name)]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous video {name}: {', '.join(p.name for p in matches)}. Keep one matching file or use exact label filenames.")
        if matches:
            resolved[name] = matches[0]
        else:
            missing.append(name)
    if missing:
        raise ValueError(f"Missing {len(missing)} labelled videos in {directory}: {', '.join(missing)}. "
                         "Set --videos-dir to the folder containing all labelled videos. No cases were silently skipped.")
    return resolved


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="2b")
    p.add_argument("--device", default=None)
    p.add_argument("--model-path", type=Path)
    p.add_argument("--quantization", choices=("none", "4bit"), default="none")
    p.add_argument("--out", type=Path, default=BACKEND / "var/semantic_benchmark_2b")
    p.add_argument("--videos-dir", type=Path, default=BACKEND.parent / "data/open/videos")
    p.add_argument("--labels", type=Path, default=BACKEND / "eval/expected_api_verdicts.json")
    p.add_argument("--videos", nargs="+", help="Optional video stems for a smoke run; default all videos")
    p.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    p.add_argument("--baseline", choices=("cached", "fresh"), default="fresh")
    p.add_argument("--offline", action="store_true", help="Require model files already downloaded locally")
    p.add_argument("--cache", type=Path, default=BACKEND / "var/tuning")
    p.add_argument("--tuning", type=Path, default=BACKEND / "var/tuning/results/tuning-regions2.json")
    p.add_argument("--window-seconds", type=float, default=8)
    p.add_argument("--stride-seconds", type=float, default=4)
    p.add_argument("--window-frames", type=int, default=6)
    p.add_argument("--caption-tokens", type=int, default=96)
    p.add_argument("--semantic-threshold", type=float, default=0.75)
    p.add_argument("--followup-max-calls", type=int, default=3)
    p.add_argument("--followup-frames", type=int, default=4)
    p.add_argument("--structured-tokens", type=int, default=512)
    p.add_argument("--call-seconds", type=float, default=45)
    p.add_argument("--score-only", action="store_true", help="Print saved results without loading models")
    args = p.parse_args()
    if args.followup_max_calls < 0 or args.followup_frames < 1 or args.call_seconds <= 0:
        p.error("Follow-up budget must be nonnegative; frames and call time must be positive")
    if not 0 < args.stride_seconds <= args.window_seconds or args.window_frames < 2 or args.caption_tokens < 1:
        p.error("Require 0 < stride <= window, at least two frames and positive caption tokens")
    if not 0.5 < args.semantic_threshold < 1 or args.structured_tokens < 1:
        p.error("Require 0.5 < semantic threshold < 1 and positive structured tokens")
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    return args


def prepare(args, labels, video_paths):
    args.out.mkdir(parents=True, exist_ok=True)
    files = [p for p in (BACKEND / "src").rglob("*") if p.suffix in {".py", ".yaml", ".json"}]
    files += list((BACKEND / "eval/tuning").glob("*.py"))
    files += [BACKEND / "eval/benchmark_semantics.py", BACKEND / "eval/semantic_benchmark_metrics.py",
              args.labels, BACKEND / "eval/reconstruction_annotations.json", BACKEND / "eval/dataset_labels.json",
              BACKEND / "eval/violation_times.json"]
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items() if k != "score_only"}
    config["source_sha256"] = {str(p.relative_to(BACKEND)) if p.is_relative_to(BACKEND) else str(p): sha(p) for p in files}
    config["video_sha256"] = {name: sha(video_paths[name]) for name in labels}
    config["video_paths"] = {name: str(video_paths[name]) for name in labels}
    config["tuning_sha256"] = sha(args.tuning) if args.tuning.exists() else None
    caches = []
    if args.baseline == "cached":
        calibration_names = read_json(args.labels)
        for folder, suffix in (("probes/base-full", ".json"), ("probes/regions", ".json"), ("probes/regions2", ".json"),
                               ("scene", ".json"), ("pose", ".json"), ("motion", ".npz")):
            for name in (calibration_names if folder.startswith("probes/") else labels):
                path = args.cache / folder / (Path(name).stem + suffix)
                if not path.exists():
                    raise ValueError(f"Missing baseline cache {path}. Use --baseline fresh to generate observations.")
                caches.append(path)
    config["cache_sha256"] = {str(p.relative_to(args.cache)): sha(p) for p in caches}
    manifest = args.out / "manifest.json"
    if manifest.exists():
        saved = read_json(manifest)
        if saved["config"] != config:
            raise ValueError("Source, settings, labels or inputs changed. Choose a new --out directory.")
        for relative, digest in saved["snapshot_sha256"].items():
            path = args.out / relative
            if not path.is_file() or sha(path) != digest:
                raise ValueError(f"Frozen input changed: {relative}. Choose a new --out directory.")
        return args.out / "snapshot/backend"
    snapshot = args.out / "snapshot/backend"
    shutil.copytree(BACKEND / "src", snapshot / "src", ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    shutil.copytree(BACKEND / "eval/tuning", snapshot / "eval/tuning", ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    for name in ("reconstruction_annotations.json", "dataset_labels.json", "violation_times.json",
                 "benchmark_semantics.py", "semantic_benchmark_metrics.py"):
        shutil.copy2(BACKEND / "eval" / name, snapshot / "eval" / name)
    shutil.copy2(args.labels, snapshot / "eval/expected_api_verdicts.json")
    if args.tuning.exists():
        shutil.copy2(args.tuning, args.out / "tuning.json")
    for path in caches:
        target = snapshot / "var/tuning" / path.relative_to(args.cache)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    snapshot_hashes = {str(p.relative_to(args.out)): sha(p) for p in snapshot.rglob("*") if p.is_file()}
    if (args.out / "tuning.json").exists():
        snapshot_hashes["tuning.json"] = sha(args.out / "tuning.json")
    write(manifest, {"started_utc": datetime.now(timezone.utc).isoformat(), "config": config,
                     "snapshot_sha256": snapshot_hashes})
    return snapshot


def summarize(out, labels, hashes, methods):
    from semantic_benchmark_metrics import aggregate
    rows = {method: [] for method in methods}
    for method in methods:
        for video in labels:
            path = out / Path(video).stem / method / "result.json"
            if path.exists():
                rows[method].append(read_json(path))
    metrics, unique = {}, {}
    for method, values in rows.items():
        metrics[method] = aggregate(values)
        dedup = {}
        for value in values:
            dedup.setdefault(hashes[value["video"]], value)
        unique[method] = aggregate(list(dedup.values()))
    common = set(labels)
    for values in rows.values():
        common &= {r["video"] for r in values if r["status"] == "done"}
    paired = {m: aggregate([r for r in values if r["video"] in common]) for m, values in rows.items()}
    write(out / "summary.json", {"planned_videos": len(labels), "methods": metrics,
                                "unique_content": unique, "paired_common_completed": paired,
                                "paired_videos": sorted(common)})
    fields = ["method", "video", "expected", "predicted", "status", "correct", "seconds", "model_calls",
              "model_cache_hits", "followup_errors", "aspects_hit", "aspects_total", "time_error", "error"]
    with (out / "comparison.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for values in rows.values():
            writer.writerows(values)
    percent = lambda n: f"{n:.1%}" if n is not None else "-"
    lines = ["# Semantic video benchmark", "", "Accuracy counts failed attempts as incorrect. Partial results show attempted videos only. "
             "These are development videos, not a held-out test. Timeline F1 treats unknown samples as errors. "
             "See summary.json for unique-video scores and a comparison restricted to videos completed by every method.", "",
             "| Method | Done/planned | Failed | Accuracy | Precision | Recall | F1 | Timeline F1 | Aspect recall | Follow-up errors | Seconds |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method, m in metrics.items():
        lines.append(f"| {method} | {m['completed']}/{len(labels)} | {m['failed']} | {percent(m['accuracy'])} | "
                     f"{percent(m['precision'])} | {percent(m['recall'])} | {percent(m['f1'])} | "
                     f"{percent(m['timeline_macro_f1'])} | {percent(m['aspect_recall'])} | {m['followup_errors']} | {m['seconds']:.1f} |")
    lines += ["", "Times include work performed in this invocation; cache hits are reported separately. "
              "Cached baseline scores omit earlier perception inference cost. Call time limits are cooperative "
              "generation stopping limits, not hard GPU deadlines. Inspect raw captions, calls and follow-up "
              "records to understand any score changes.", "", "| Method | Video | Expected | Predicted | Match |",
              "|---|---|---|---|---|"]
    for values in rows.values():
        for row in values:
            lines.append(f"| {row['method']} | {row['video']} | {row['expected']} | {row['predicted'] or 'ERROR'} | {row['correct']} |")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nMethod                       done  accuracy  precision recall  F1     timelineF1 errors", flush=True)
    for method, m in metrics.items():
        print(f"{method:28s} {m['completed']:2d}/{len(labels):2d} {percent(m['accuracy']):>8s} "
              f"{percent(m['precision']):>9s} {percent(m['recall']):>6s} {percent(m['f1']):>6s} "
              f"{percent(m['timeline_macro_f1']):>10s} {m['followup_errors']:3d}", flush=True)


def main():
    args = arguments()
    if args.score_only:
        manifest = read_json(args.out / "manifest.json")
        frozen = args.out / "snapshot/backend"
        sys.path[:0] = [str(frozen / "src"), str(frozen / "eval")]
        cfg = manifest["config"]
        labels = read_json(frozen / "eval/expected_api_verdicts.json")
        labels = {k:v for k,v in labels.items() if k in cfg["video_sha256"]}
        summarize(args.out, labels, cfg["video_sha256"], cfg["methods"])
        return
    labels = read_json(args.labels)
    if not labels or any(v not in {"violation", "no_violation"} for v in labels.values()):
        raise ValueError("Expected a nonempty filename-to-verdict label mapping")
    if args.videos:
        requested = {video_key(v) for v in args.videos}
        labels = {k:v for k,v in labels.items() if video_key(k) in requested}
        if {video_key(k) for k in labels} != requested:
            raise ValueError("Unknown video stem requested")
    video_paths = resolve_videos(args.videos_dir, labels)
    args.out.mkdir(parents=True, exist_ok=True)
    run_lock = (args.out / ".run.lock").open("a+")
    if sys.platform != "win32":
        import fcntl
        try:
            fcntl.flock(run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another benchmark is using this --out directory") from error
    frozen = prepare(args, labels, video_paths)
    sys.path[:0] = [str(frozen / "src"), str(frozen / "eval"), str(frozen / "eval/tuning")]
    import common
    common.VIDEOS = args.videos_dir
    from backend.followup.pipeline import refine
    from backend.perception.pipeline import PerceptionReconstructor
    from backend.reconstruction.graph import build_timeline
    from backend.reconstruction.video import decode
    from backend.rules.engine import evaluate
    from backend.rules.registry import load_registry
    from backend.rules.verdict import ReportingPolicy, reportable
    from backend.semantic.captions import CaptionConfig, describe_windows, caption_graph
    from backend.semantic.followup import TextObserver, TextSemanticMatcher, refresh_derived_states
    from backend.semantic.vlm import TextVLM
    from common import score_video
    from fused_bench import Experiment, build
    from run_tuning import base_config, knobs
    registry, policy = load_registry(), ReportingPolicy(production_only=False)
    from backend.perception.settings import load_config
    from backend.reconstruction.vlm import MODEL_IDS
    config = base_config("regions+regions2") if args.baseline == "cached" else load_config(MODEL_IDS.get(args.model, args.model))
    if args.baseline == "cached" and (args.out / "tuning.json").exists():
        state = read_json(args.out / "tuning.json")["state"]
        for knob in knobs():
            knob.apply(config, state.get(knob.name, knob.start))
    captions_config = CaptionConfig(args.window_seconds, args.stride_seconds, args.window_frames,
                                   args.caption_tokens, threshold=args.semantic_threshold)
    write(args.out / "protocol.json", {"baseline_config": asdict(config), "caption_config": asdict(captions_config),
                                     "methods": args.methods, "positive_verdict_rechecks": True,
                                     "timeline_unknowns": "count as errors", "labels_used_by_analyzer": False})
    annotations = read_json(frozen / "eval/reconstruction_annotations.json")
    from semantic_benchmark_metrics import score_timeline
    model = None
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    def get_model():
        nonlocal model
        if model is None:
            print("Loading model", args.model, flush=True)
            model = TextVLM(args.model, args.model_path, args.device, args.quantization,
                            cache_dir=args.out / "model_calls", call_seconds=args.call_seconds,
                            structured_tokens=args.structured_tokens, local_files_only=args.offline)
            print(f"Loaded {model.name} on {model.device}", flush=True)
        return model
    hashes = read_json(args.out / "manifest.json")["config"]["video_sha256"]
    for number, (name, target) in enumerate(labels.items(), 1):
        pending = [m for m in args.methods if not (args.out / Path(name).stem / m / "result.json").exists()
                   or read_json(args.out / Path(name).stem / m / "result.json")["status"] != "done"]
        if not pending:
            print(f"Skip {number}/{len(labels)} {name}: all methods complete", flush=True)
            continue
        print(f"\nVIDEO {number}/{len(labels)} {name}", flush=True)
        baseline = video = captions = None
        setup_started = time.perf_counter()
        try:
            baseline = (build(Experiment("baseline", "base-full", "regions+regions2", config), Path(name).stem)
                        if args.baseline == "cached" else PerceptionReconstructor(get_model(), config).run(video_paths[name]))
            if baseline is None:
                raise ValueError("Missing baseline observations")
            if baseline.observer_model != MODEL_IDS.get(args.model, args.model):
                raise ValueError("Cached baseline uses another model. Use --baseline fresh.")
            baseline_graph = build_timeline(baseline)
            baseline_graph.video.id = Path(name).stem
        except Exception as error:
            for method in pending:
                directory = args.out / Path(name).stem / method
                write(directory / "result.json", {"method": method, "video": name, "expected": target,
                      "predicted": None, "correct": False, "status": "failed", "seconds": time.perf_counter()-setup_started,
                      "error": "Baseline setup failed: " + str(error)})
            summarize(args.out, labels, hashes, args.methods)
            continue
        for method in pending:
            directory = args.out / Path(name).stem / method
            began, call_start = time.perf_counter(), len(model.calls) if model else 0
            row = {"method": method, "video": name, "expected": target, "predicted": None, "correct": False,
                   "status": "failed", "followup_errors": 0}
            print(f"  START {method}", flush=True)
            try:
                graph = baseline_graph.model_copy(deep=True)
                if method != "baseline" and video is None:
                    video = decode(video_paths[name], 2)
                if method in {"captions_only", "baseline_captions", "captions_followups"}:
                    if captions is None:
                        captions = describe_windows(get_model(), video, captions_config,
                                                    lambda message: print("    " + message, flush=True))
                        write(args.out / Path(name).stem / "captions.json", captions)
                    graph = caption_graph(video, captions, captions_config, get_model().name,
                                          baseline if method == "baseline_captions" else None)
                    graph.video.id = Path(name).stem
                if method in {"structured_followups", "plain_followups", "captions_followups"}:
                    observer = semantic = None
                    if method != "structured_followups":
                        observer = TextObserver(get_model(), video, args.followup_frames)
                        semantic = TextSemanticMatcher(get_model(), registry.rules)
                    result = refine(registry, graph, video, get_model(), max_calls=args.followup_max_calls,
                                    max_frames=args.followup_frames, observer=observer, semantic_matcher=semantic,
                                    verify_positive=True, post_merge=refresh_derived_states)
                    graph = result.graph
                    row["followup_errors"] = len(result.semantic_errors) + sum(r.error is not None for r in result.checks)
                    row["followup_calls"] = result.calls
                    write(directory / "followups.json", {"checks": [r.model_dump(mode="json") for r in result.checks],
                          "semantic_errors": result.semantic_errors,
                          "plain_text": observer.records if observer else []})
                report = evaluate(registry, graph, "shadow")
                findings = [{"rule_id": f.rule_id, "timecode_sec": f.timecode_sec,
                             "outcome": f.outcome, "kind": f.unknown_kind} for f in reportable(report, policy)]
                # Ground truth is read here for scoring, after inference and rule evaluation.
                row.update(score_video(name, findings))
                row.update(status="done", findings=findings, timeline=score_timeline(graph, annotations))
                write(directory / "timeline.steg.json", graph.model_dump(mode="json"))
                write(directory / "rule_report.json", report.model_dump(mode="json"))
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {error}"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
                print("    ERROR", row["error"], flush=True)
            finally:
                calls = model.calls[call_start:] if model else []
                row.update(seconds=time.perf_counter()-began, model_calls=sum(not c.get("cache_hit") for c in calls),
                           model_cache_hits=sum(bool(c.get("cache_hit")) for c in calls))
                write(directory / "calls.json", calls)
                write(directory / "result.json", row)
            print(f"  DONE {method}: {row['predicted']} expected={target} match={row['correct']} "
                  f"{row['seconds']:.1f}s errors={row['followup_errors']}", flush=True)
            summarize(args.out, labels, hashes, args.methods)
        gc.collect()
        if model is not None and model.device == "mps":
            import torch
            torch.mps.empty_cache()
    summarize(args.out, labels, hashes, args.methods)
    print(f"\nReport: {args.out / 'REPORT.md'}\nRaw scores: {args.out / 'summary.json'}", flush=True)


if __name__ == "__main__":
    main()

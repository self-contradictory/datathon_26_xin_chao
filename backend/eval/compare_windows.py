"""Run the per-frame question baseline and both sliding-window observers on the same videos.

Usage: .venv/bin/python -B eval/compare_windows.py --model 4b --videos Х-15 Х-3
Outputs go to var/compare_windows/<model>/<video>/<approach>/; finished runs are skipped,
and saved window outputs are re-assembled without calling the model again.
"""
import argparse
import json
import time
from pathlib import Path

from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import Reconstruction, Reconstructor
from backend.reconstruction.video import decode
from backend.rules.engine import evaluate
from backend.rules.registry import load_registry
from backend.windows.model import WindowVLM
from backend.windows.models import Window
from backend.windows.observers import CaptionObserver, StructuredObserver
from backend.windows.pipeline import WindowPipeline

BACKEND = Path(__file__).resolve().parents[1]
VIDEOS = BACKEND.parent / "data" / "open" / "videos"
OUTPUT = BACKEND / "var" / "compare_windows"


def save(directory: Path, reconstruction: Reconstruction, graph, report, run: dict) -> None:
    tracks = {key: {"segments": [{"start": s.start, "end": s.end, "value": s.value, "confidence": s.confidence}
                                 for s in track.segments],
                    "observations": [[o.time, o.probability] for o in track.observations]}
              for key, track in reconstruction.tracks.items()}
    (directory / "tracks.json").write_text(json.dumps(tracks))
    (directory / "steg.json").write_text(graph.model_dump_json(indent=1))
    (directory / "report.json").write_text(report.model_dump_json(indent=1))
    (directory / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="4b")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--device", help="PyTorch device, for example cuda or cuda:0")
    parser.add_argument("--quantization", choices=["none", "4bit"], default="none")
    parser.add_argument("--videos", nargs="+", default=["Х-15", "Х-3"])
    parser.add_argument("--approaches", nargs="+", default=["questions", "structured", "structured_dense", "caption"])
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    began = time.perf_counter()
    vlm = WindowVLM(args.model, args.model_path, args.device, args.quantization)
    model_tag = args.model if args.quantization == "none" else f"{args.model}-{args.quantization}"
    registry = load_registry()
    print(f"loaded {vlm.name} on {vlm.device} in {time.perf_counter() - began:.1f}s", flush=True)
    for name in args.videos:
        path = VIDEOS / f"{name}.mov"
        for approach in args.approaches:
            directory = args.out / model_tag / name / approach
            if (directory / "run.json").exists():
                print(f"skip {name} {approach}", flush=True)
                continue
            directory.mkdir(parents=True, exist_ok=True)
            began = time.perf_counter()
            if approach == "questions":
                reconstruction = Reconstructor(vlm, 1.0, 256).run(path)
                graph = build_timeline(reconstruction)
                report = evaluate(registry, graph, "shadow")
                run = {"observe_seconds": time.perf_counter() - began, "semantic_calls": 0, "semantic_errors": []}
            else:
                observer = (CaptionObserver(vlm) if approach == "caption"
                            else StructuredObserver(vlm, dense=approach == "structured_dense"))
                pipeline = WindowPipeline(observer, vlm, registry)
                cached = directory / "windows.json"
                if cached.exists():
                    video = decode(path, pipeline.sample_fps)
                    windows = [Window.model_validate(item) for item in json.loads(cached.read_text())]
                else:
                    def report_window(window: Window) -> None:
                        print(f"  {name} {approach} window {window.index} {window.start_sec:.1f}-{window.end_sec:.1f}s "
                              f"{window.seconds} {'ERROR ' + window.error[:80] if window.error else 'ok'}", flush=True)

                    video, windows = pipeline.observe(path, report_window)
                    cached.write_text(json.dumps([window.model_dump(mode="json") for window in windows],
                                                 ensure_ascii=False, indent=1))
                observed = time.perf_counter() - began
                result = pipeline.assemble(video, windows)
                reconstruction, graph, report = result.reconstruction, result.graph, result.report
                run = {"observe_seconds": observed, "semantic_calls": result.semantic_calls,
                       "semantic_errors": result.semantic_errors,
                       "windows": len(windows), "parse_failures": sum(window.error is not None for window in windows)}
            run |= {"model": vlm.name, "quantization": args.quantization,
                    "device": vlm.device, "video": name, "approach": approach,
                    "total_seconds": time.perf_counter() - began}
            save(directory, reconstruction, graph, report, run)
            verdicts = [(f.rule_id.split("-")[0], f.outcome, round(f.timecode_sec, 1))
                        for f in report.findings("VIOLATION")]
            print(f"done {name} {approach} in {run['total_seconds']:.0f}s violations={verdicts}", flush=True)


if __name__ == "__main__":
    main()

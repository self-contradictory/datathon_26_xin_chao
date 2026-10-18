"""Run the API analyzer path (PerceptionReconstructor + QuestionAnalyzer) on real videos and time it.

    .venv/bin/python -B eval/tuning/e2e_check.py Х-26 Х-27
"""
import sys
import time

from backend.analyzers.questions import QuestionAnalyzer
from backend.perception.pipeline import PerceptionReconstructor
from backend.perception.settings import load_config
from backend.reconstruction.vlm import QuestionVLM
from backend.rules.verdict import verdict
from common import VIDEOS, expected

if __name__ == "__main__":
    began = time.perf_counter()
    model = QuestionVLM("2b")
    analyzer = QuestionAnalyzer(PerceptionReconstructor(model, load_config(model.name)))
    print(f"loaded in {time.perf_counter() - began:.1f}s", flush=True)
    labels = expected()
    for stem in sys.argv[1:]:
        path = VIDEOS / f"{stem}.mov"
        began = time.perf_counter()
        violations = analyzer.analyze(path)
        print(f"{stem}: {verdict(violations)} (label {labels[path.name]}) in {time.perf_counter() - began:.1f}s")
        for item in violations:
            print(f"  {item.timecode_sec:6.1f}s {item.type}")

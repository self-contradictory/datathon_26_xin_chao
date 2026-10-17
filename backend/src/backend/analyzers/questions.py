from pathlib import Path

from backend.analyzers.base import VideoAnalyzer
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import Reconstructor
from backend.rules.engine import evaluate
from backend.rules.findings import Mode
from backend.rules.registry import load_registry
from backend.rules.verdict import ReportingPolicy, reportable, to_violations
from backend.schemas import Violation


class QuestionAnalyzer(VideoAnalyzer):
    def __init__(self, reconstructor: Reconstructor, mode: Mode = "shadow") -> None:
        self.reconstructor = reconstructor
        self.registry = load_registry()
        self.mode = mode
        self.policy = ReportingPolicy(production_only=mode == "production")

    def analyze(self, video_path: Path) -> list[Violation]:
        reconstruction = self.reconstructor.run(video_path)
        timeline = build_timeline(reconstruction)
        report = evaluate(self.registry, timeline, self.mode)
        return to_violations(reportable(report, self.policy), reconstruction.video.jpeg_at)

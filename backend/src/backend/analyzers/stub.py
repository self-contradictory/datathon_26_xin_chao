from pathlib import Path

from backend.analyzers.base import VideoAnalyzer
from backend.schemas import Violation


class StubAnalyzer(VideoAnalyzer):
    def analyze(self, video_path: Path) -> list[Violation]:
        return []

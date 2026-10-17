from abc import ABC, abstractmethod
from pathlib import Path

from backend.schemas import Violation


class VideoAnalyzer(ABC):
    @abstractmethod
    def analyze(self, video_path: Path) -> list[Violation]: ...

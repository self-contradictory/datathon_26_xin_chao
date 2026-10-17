from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import batched
from pathlib import Path

from backend.followup.models import StructuredModel
from backend.followup.semantic import SemanticMatcher
from backend.reconstruction.pipeline import Reconstruction
from backend.reconstruction.video import DecodedVideo, decode
from backend.rules.engine import evaluate, select_rules
from backend.rules.findings import EvaluationReport, Mode
from backend.rules.models import Rule, RuleRegistry
from backend.steg import SparseTemporalEvidenceGraph
from backend.windows.assemble import OPEN_PREFIX, claims, reconstruct, timeline
from backend.windows.clips import clips
from backend.windows.models import Window
from backend.windows.observers import WindowObserver


@dataclass(slots=True)
class WindowRun:
    windows: list[Window]
    reconstruction: Reconstruction
    graph: SparseTemporalEvidenceGraph
    report: EvaluationReport
    semantic_calls: int = 0
    semantic_errors: list[str] = field(default_factory=list)


def match_open_vocabulary(model: StructuredModel, rules: list[Rule], graph: SparseTemporalEvidenceGraph,
                          max_calls: int = 4, batch: int = 6) -> tuple[SparseTemporalEvidenceGraph, int, list[str]]:
    matcher = SemanticMatcher(model, rules)
    pending = [item for item in matcher.candidates(graph, limit=10**6)
               if item["kind"] == "action" and item["record_id"].startswith(OPEN_PREFIX)]
    calls, errors = 0, []
    for chunk in list(batched(pending, batch))[:max_calls]:
        calls += 1
        try:
            graph = matcher.run(graph, list(chunk))
        except ValueError as error:
            errors.append(str(error))
    return graph, calls, errors


class WindowPipeline:
    def __init__(self, observer: WindowObserver, model: StructuredModel, registry: RuleRegistry,
                 mode: Mode = "shadow", sample_fps: float = 2.0, window_sec: float = 6.0,
                 stride_sec: float = 3.0, image_tokens: int = 256, semantic_calls: int = 4) -> None:
        self.observer, self.model, self.registry, self.mode = observer, model, registry, mode
        self.sample_fps, self.window_sec, self.stride_sec = sample_fps, window_sec, stride_sec
        self.image_tokens, self.semantic_calls = image_tokens, semantic_calls

    def observe(self, path: Path, on_window: Callable[[Window], None] | None = None,
                ) -> tuple[DecodedVideo, list[Window]]:
        video = decode(path, self.sample_fps)
        windows = []
        for clip in clips(video, self.window_sec, self.stride_sec, self.image_tokens):
            windows.append(self.observer.observe(clip))
            if on_window is not None:
                on_window(windows[-1])
        return video, windows

    def assemble(self, video: DecodedVideo, windows: list[Window]) -> WindowRun:
        observed = [claims(window) for window in windows if window.graph is not None]
        reconstruction = reconstruct(video, observed, getattr(self.model, "name", "unknown"))
        graph = timeline(reconstruction, observed, self.window_sec, self.stride_sec,
                         f"windows-{self.observer.name}-v1")
        graph, calls, errors = match_open_vocabulary(
            self.model, select_rules(self.registry.rules, self.mode), graph, self.semantic_calls,
        )
        return WindowRun(windows, reconstruction, graph, evaluate(self.registry, graph, self.mode), calls, errors)

    def run(self, path: Path) -> WindowRun:
        return self.assemble(*self.observe(path))

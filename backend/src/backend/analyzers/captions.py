"""Optional video analyzer for ordinary prose descriptions and semantic rule matching."""
from pathlib import Path

from backend.analyzers.base import VideoAnalyzer
from backend.followup.pipeline import refine
from backend.reconstruction.video import decode
from backend.rules.engine import evaluate
from backend.rules.registry import load_registry
from backend.rules.verdict import ReportingPolicy, reportable, to_violations
from backend.semantic.captions import CaptionConfig, caption_graph, describe_windows
from backend.semantic.followup import TextObserver, TextSemanticMatcher, refresh_derived_states
from backend.semantic.vlm import atomic_json


class CaptionAnalyzer(VideoAnalyzer):
    """Generates prose only. Application code owns the graph and its validated IDs.

    Pass a TextVLM-compatible model. An optional baseline reconstructor keeps its evidence
    when the descriptions omit a fact. This analyzer is opt-in and does not replace API defaults.
    """
    def __init__(self, model, config=CaptionConfig(), baseline=None, max_followup_calls=3,
                 followup_frames=4, output_dir: Path | None = None):
        self.model, self.config, self.baseline = model, config, baseline
        self.max_followup_calls, self.followup_frames = max_followup_calls, followup_frames
        self.output_dir = output_dir
        self.registry = load_registry()

    def analyze(self, video_path: Path):
        video = decode(video_path, 2)
        baseline = self.baseline.run(video_path) if self.baseline else None
        captions = describe_windows(self.model, video, self.config)
        graph = caption_graph(video, captions, self.config, self.model.name, baseline)
        result = refine(self.registry, graph, video, self.model, max_calls=self.max_followup_calls,
                        max_frames=self.followup_frames, observer=TextObserver(self.model, video, self.followup_frames),
                        semantic_matcher=TextSemanticMatcher(self.model, self.registry.rules),
                        verify_positive=True, post_merge=refresh_derived_states)
        if self.output_dir is not None:
            directory = self.output_dir / video_path.stem
            atomic_json(directory / "captions.json", captions)
            atomic_json(directory / "timeline.steg.json", result.graph.model_dump(mode="json"))
            atomic_json(directory / "followups.json", {"calls": result.calls,
                        "checks": [r.model_dump(mode="json") for r in result.checks], "errors": result.semantic_errors})
        def jpeg(moment):
            return result.frame_images.get(moment) or video.jpeg_at(moment)
        return to_violations(reportable(result.report, ReportingPolicy(production_only=False)), jpeg)

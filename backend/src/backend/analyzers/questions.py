import logging
from pathlib import Path

from backend.analyzers.base import VideoAnalyzer
from backend.followup.pipeline import refine
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import Reconstructor
from backend.semantic.captions import CaptionConfig, caption_graph, describe_windows
from backend.semantic.vlm import TextVLM, atomic_json
from backend.rules.findings import Mode
from backend.rules.registry import load_registry
from backend.rules.verdict import ReportingPolicy, reportable, to_violations
from backend.schemas import Violation

logger = logging.getLogger(__name__)


class QuestionAnalyzer(VideoAnalyzer):
    def __init__(self, reconstructor: Reconstructor, mode: Mode = "shadow",
                 max_followup_calls: int = 2, followup_frames: int = 2,
                 timeline_dir: Path | None = None, temporal_scan: bool = True) -> None:
        self.reconstructor = reconstructor
        self.registry = load_registry()
        self.mode = mode
        self.policy = ReportingPolicy(production_only=mode == "production")
        self.max_followup_calls = max_followup_calls
        self.followup_frames = followup_frames
        self.timeline_dir = timeline_dir
        self.temporal_scan = temporal_scan
        if (max_followup_calls or temporal_scan) and not hasattr(reconstructor.vlm, "entail"):
            cache_root = timeline_dir.parent if timeline_dir else Path(__file__).resolve().parents[3] / "var"
            reconstructor.vlm = TextVLM.wrap(reconstructor.vlm, cache_root / "model_calls")

    def analyze(self, video_path: Path) -> list[Violation]:
        reconstruction = self.reconstructor.run(video_path)
        timeline = build_timeline(reconstruction)
        captions = []
        if self.temporal_scan:
            try:
                config = CaptionConfig()
                captions = describe_windows(self.reconstructor.vlm, reconstruction.video, config)
                timeline = caption_graph(reconstruction.video, captions, config,
                                         self.reconstructor.vlm.name, baseline=reconstruction)
            except Exception:
                logger.exception("Video %s: caption scan failed; using per-frame answers", video_path.stem)
        try:
            result = refine(self.registry, timeline, reconstruction.video, self.reconstructor.vlm,
                            self.mode, self.max_followup_calls, self.followup_frames)
        except Exception:
            logger.exception("Video %s: follow-ups failed; evaluating rules without them", video_path.stem)
            result = refine(self.registry, timeline, reconstruction.video, self.reconstructor.vlm,
                            self.mode, 0, self.followup_frames)
        try:
            self._write_timeline(timeline, result, captions)
        except OSError:
            logger.exception("Video %s: could not write the timeline", video_path.stem)

        def frame_jpeg(moment: float) -> bytes:
            if moment in result.frame_images:
                return result.frame_images[moment]
            return reconstruction.video.jpeg_at(moment)

        return to_violations(reportable(result.report, self.policy), frame_jpeg)

    def _write_timeline(self, timeline, result, captions) -> None:
        if self.timeline_dir is not None:
            self.timeline_dir.mkdir(parents=True, exist_ok=True)
            atomic_json(self.timeline_dir / f"{timeline.video.id}.steg.json", result.graph.model_dump(mode="json"))
            atomic_json(self.timeline_dir / f"{timeline.video.id}.captions.json", captions)
            atomic_json(self.timeline_dir / f"{timeline.video.id}.followups.json", {
                "visual_checks": result.calls,
                "semantic_calls": result.semantic_calls,
                "caption_windows": len(captions),
                "checks": [record.model_dump(mode="json") for record in result.checks],
                "semantic_errors": result.semantic_errors,
                "plain_text": result.plain_text_records,
            })

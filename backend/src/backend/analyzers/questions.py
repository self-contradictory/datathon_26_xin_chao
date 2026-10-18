import json
import logging
from pathlib import Path

from backend.analyzers.base import VideoAnalyzer
from backend.followup.pipeline import refine
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import Reconstructor
from backend.reconstruction.temporal import observe_cash_provenance
from backend.rules.findings import Mode
from backend.rules.registry import load_registry
from backend.rules.verdict import ReportingPolicy, reportable, to_violations
from backend.schemas import Violation

logger = logging.getLogger(__name__)


class QuestionAnalyzer(VideoAnalyzer):
    def __init__(self, reconstructor: Reconstructor, mode: Mode = "shadow",
                 max_followup_calls: int = 0, followup_frames: int = 8,
                 timeline_dir: Path | None = None, temporal_scan: bool = False) -> None:
        self.reconstructor = reconstructor
        self.registry = load_registry()
        self.mode = mode
        self.policy = ReportingPolicy(production_only=mode == "production")
        self.max_followup_calls = max_followup_calls
        self.followup_frames = followup_frames
        self.timeline_dir = timeline_dir
        self.temporal_scan = temporal_scan

    def analyze(self, video_path: Path) -> list[Violation]:
        reconstruction = self.reconstructor.run(video_path)
        timeline = build_timeline(reconstruction)
        temporal = None
        if self.temporal_scan:
            try:
                temporal = observe_cash_provenance(timeline, reconstruction.video, self.reconstructor.vlm)
                timeline = temporal.graph
            except Exception:
                logger.exception("Video %s: temporal scan failed; using per-frame answers", video_path.stem)
        try:
            result = refine(self.registry, timeline, reconstruction.video, self.reconstructor.vlm,
                            self.mode, self.max_followup_calls, self.followup_frames)
        except Exception:
            logger.exception("Video %s: follow-ups failed; evaluating rules without them", video_path.stem)
            result = refine(self.registry, timeline, reconstruction.video, self.reconstructor.vlm,
                            self.mode, 0, self.followup_frames)
        try:
            self._write_timeline(timeline, result, temporal)
        except OSError:
            logger.exception("Video %s: could not write the timeline", video_path.stem)

        def frame_jpeg(moment: float) -> bytes:
            if moment in result.frame_images:
                return result.frame_images[moment]
            return reconstruction.video.jpeg_at(moment)

        return to_violations(reportable(result.report, self.policy), frame_jpeg)

    def _write_timeline(self, timeline, result, temporal) -> None:
        if self.timeline_dir is not None:
            self.timeline_dir.mkdir(parents=True, exist_ok=True)
            (self.timeline_dir / f"{timeline.video.id}.steg.json").write_text(result.graph.model_dump_json(indent=2))
            (self.timeline_dir / f"{timeline.video.id}.followups.json").write_text(json.dumps({
                "model_calls": result.calls,
                "temporal_calls": temporal.calls if temporal else 0,
                "temporal_errors": temporal.errors if temporal else [],
                "checks": [record.model_dump(mode="json") for record in result.checks],
                "semantic_errors": result.semantic_errors,
            }, ensure_ascii=False, indent=2))

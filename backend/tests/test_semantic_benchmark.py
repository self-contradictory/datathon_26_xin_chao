import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from backend.followup.merge import merge_answer
from backend.followup.models import EvidenceQuestion, TimeWindow
from backend.followup.observer import ReplayFrame
from backend.followup.pipeline import refine
from backend.followup.planner import plan_questions
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.probes import PERCEPTION_PROBES
from backend.reconstruction.video import DecodedVideo
from backend.rules.engine import evaluate
from backend.rules.models import EntityByKind, StateMatcher
from backend.rules.registry import load_registry
from backend.semantic.captions import CaptionConfig, caption_probabilities, reconstruct_captions, windows
from backend.semantic.followup import TextObserver
from backend.steg import EvidenceFrame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from semantic_benchmark_metrics import aggregate, score_timeline
from test_perception import timeline


def video():
    _, image = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    return DecodedVideo(Path("synthetic.mov"), 8.0, 2.0, 32, 32, 2.0,
                        np.arange(0, 8, .5), list(range(16)), [image.tobytes()] * 16)


def caption(start, end, values):
    return {"start": start, "end": end, "scores":
            {p.key: values.get(p.key, [0.01, 0.01, 0.98]) for p in PERCEPTION_PROBES}}


class CaptionTests(unittest.TestCase):
    def test_windows_cover_tail_without_extra_duplicate_window(self):
        config = CaptionConfig(window_seconds=8, stride_seconds=4)
        self.assertEqual(list(windows(8, config)), [(0, 8)])
        self.assertEqual(list(windows(13, config)), [(0, 8), (4, 12), (8, 13)])
        with self.assertRaises(ValueError):
            CaptionConfig(window_seconds=4, stride_seconds=8)

    def test_unmentioned_facts_stay_unknown_through_hmm_and_graph(self):
        source = video()
        captions = [caption(0, 4, {"room_occupied": [.99, .005, .005]}), caption(4, 8, {})]
        recon = reconstruct_captions(source, captions, CaptionConfig(), "fake")
        unknown = [s for s in recon.tracks["room_occupied"].segments if s.first >= 8]
        self.assertTrue(unknown)
        self.assertTrue(all(s.confidence == .5 for s in unknown))
        graph = build_timeline(recon)
        safe = next(t for t in graph.state_tracks if t.entity_id == "safe_1" and t.property == "open")
        self.assertTrue(all(i.knowledge == "unknown" and i.value is None for i in safe.intervals))

    def test_overlap_does_not_multiply_confidence_and_contradictions_abstain(self):
        source = video()
        positive = caption(0, 8, {"cash_on_desk": [.99, .005, .005]})
        once = caption_probabilities(source, [positive], .75)["cash_on_desk"]
        twice = caption_probabilities(source, [positive, positive], .75)["cash_on_desk"]
        np.testing.assert_allclose(once, twice)
        negative = caption(0, 8, {"cash_on_desk": [.005, .99, .005]})
        np.testing.assert_allclose(caption_probabilities(source, [positive, negative], .75)["cash_on_desk"], .5)

    def test_missing_captions_preserve_baseline_in_augmented_mode(self):
        source = video()
        base = reconstruct_captions(source, [caption(0, 8, {"room_occupied": [.99, .005, .005]})], CaptionConfig(), "fake")
        augmented = reconstruct_captions(source, [caption(0, 8, {})], CaptionConfig(), "fake", base)
        self.assertEqual(base.tracks["room_occupied"].observations, augmented.tracks["room_occupied"].observations)


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.graph = timeline({"room_occupied": lambda _: True, "cashier_seated": lambda _: True,
                               "cashier_at_station": lambda _: True, "safe_open": lambda _: True,
                               "at_safe": lambda t: t < 4})
        self.registry = load_registry()

    def test_positive_alerts_are_rechecked_only_when_requested(self):
        report = evaluate(self.registry, self.graph, "shadow")
        self.assertTrue(any(f.rule_id.startswith("CD05B") for f in report.findings("VIOLATION")))
        ordinary = plan_questions(self.registry.rules, self.graph, report)
        rechecks = plan_questions(self.registry.rules, self.graph, report, True)
        self.assertFalse(any(q.rule_id.startswith("CD05B") for q in ordinary))
        self.assertTrue(any(q.rule_id.startswith("CD05B") for q in rechecks))

    def test_plain_state_answer_merges_only_actual_grounded_frames(self):
        frame = ReplayFrame(EvidenceFrame(id="test_frame", timestamp_sec=5.0, source_ref="synthetic.mov"),
                            np.zeros((32, 32, 3), np.uint8), b"jpg")
        question = EvidenceQuestion(id="test", rule_id="CD05B", matcher=StateMatcher(kind="state",
                    property="open", entity=EntityByKind(kind="object", subtype="safe"), value="true"),
                    window=TimeWindow(relation="at", start_sec=5.0, end_sec=5.0), reason="Recheck")
        class Model:
            def text(self, *args, **kwargs): return "The safe door is visibly closed."
            def entail(self, *args): return [[.01, .98, .01]]
        observer = TextObserver(Model(), video())
        with patch("backend.semantic.followup.sample_window", return_value=[frame]):
            answer, frames = observer.answer(question, self.graph)
        self.assertEqual(answer.facts[0].subject_id, "safe_1")
        self.assertEqual(answer.facts[0].value, "false")
        merged = merge_answer(self.graph, question, answer, frames)
        track = next(t for t in merged.state_tracks if t.entity_id == "safe_1" and t.property == "open")
        self.assertTrue(any(i.start_sec == 5 and i.end_sec == 5 and i.value == "false" for i in track.intervals))

    def test_failures_are_recorded_and_budget_stops_repeated_requests(self):
        class NoSemantics:
            def candidates(self, graph): return []
        class BrokenObserver:
            count = 0
            def answer(self, *args):
                self.count += 1
                raise ValueError("Bad evidence")
        observer = BrokenObserver()
        result = refine(self.registry, self.graph, video(), None, max_calls=2,
                        observer=observer, semantic_matcher=NoSemantics(), verify_positive=True)
        self.assertEqual(result.calls, observer.count)
        self.assertLessEqual(result.calls, 2)
        self.assertTrue(all(check.error for check in result.checks))
        self.assertEqual(len({c.question.id for c in result.checks}), len(result.checks))


class MetricTests(unittest.TestCase):
    def test_failures_cannot_improve_accuracy_by_disappearing(self):
        result = aggregate([{"status": "done", "expected": "no_violation", "predicted": "no_violation"},
                            {"status": "failed", "expected": "violation", "predicted": None}])
        self.assertEqual(result["accuracy"], .5)
        self.assertEqual(result["accuracy_completed"], 1)
        self.assertEqual(result["failed"], 1)

    def test_unknown_is_not_rewarded_as_a_correct_negative(self):
        graph = build_timeline(reconstruct_captions(video(), [caption(0, 8, {})], CaptionConfig(), "fake"))
        counts = score_timeline(graph, {"synthetic": {"attributes": {"safe_open": []}}})["safe_open"]
        self.assertEqual(counts["tn"], 0)
        self.assertEqual(counts["unknown"], counts["samples"])
        self.assertEqual(counts["fp"], counts["samples"])


if __name__ == "__main__":
    unittest.main()

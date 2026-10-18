import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from backend.followup.merge import merge_answer
from backend.followup.models import EvidenceQuestion, TimeWindow, VisualAnswer
from backend.followup.observer import ReplayFrame
from backend.followup.pipeline import refine
from backend.followup.planner import plan_questions
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.probes import PERCEPTION_PROBES
from backend.reconstruction.video import DecodedVideo
from backend.rules.engine import evaluate
from backend.rules.models import EntityByKind, StateMatcher, EventMatcher
from backend.rules.registry import load_registry
from backend.rules.verdict import reportable
from backend.semantic.captions import CaptionConfig, caption_probabilities, reconstruct_captions, windows
from backend.semantic.followup import TextObserver, event_participants
from backend.semantic.vlm import TextVLM
from backend.perception.scene import ground
from backend.analyzers.questions import QuestionAnalyzer
from backend.steg import EvidenceFrame, Entity

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from semantic_benchmark_metrics import aggregate, score_timeline
from benchmark_semantics import read_json, resolve_videos, write
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
                               "cashier_at_station": lambda t: t < 4, "safe_open": lambda _: True,
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

    def test_id_without_participant_mapping_still_uses_vision_and_known_actor(self):
        frame = ReplayFrame(EvidenceFrame(id="id_frame", timestamp_sec=1.0, source_ref="synthetic.mov"),
                            np.zeros((32, 32, 3), np.uint8), b"jpg")
        question = EvidenceQuestion(id="id_check", rule_id="CD12", matcher=EventMatcher(kind="event", action="physical_id_checked"),
                    window=TimeWindow(relation="before", start_sec=1.0, end_sec=1.0), reason="Missing ID evidence")
        class Model:
            calls = 0
            def text(self, *args, **kwargs):
                self.calls += 1
                return "The cashier examines the customer's passport photograph and compares it with the customer."
            def entail(self, context, questions):
                self.last_question = questions[0]
                return [[.99, .005, .005]]
            def structured(self, *args, **kwargs): raise AssertionError("Generated JSON must never be requested")
        model = Model()
        observer = TextObserver(model, video())
        with patch("backend.semantic.followup.sample_window", return_value=[frame]):
            answer, frames = observer.answer(question, self.graph)
        self.assertEqual(model.calls, 1)
        self.assertEqual(answer.actions[0].action, "physical_id_checked")
        self.assertEqual(answer.actions[0].participants[0].entity_id, "person_1")
        self.assertIn("examining or verifying", model.last_question)
        merged = merge_answer(self.graph, question, answer, frames)
        self.assertTrue(any(e.action == "physical_id_checked" for e in merged.events))

    def test_ambiguous_actor_does_not_skip_description_or_invent_binding(self):
        graph = self.graph.model_copy(deep=True)
        graph.entities.append(Entity(id="person_2", kind="person", subtype="person", role="cashier", identity_status="provisional"))
        question = EvidenceQuestion(id="ambiguous", rule_id="CD12", matcher=EventMatcher(kind="event", action="physical_id_checked"),
                    window=TimeWindow(relation="during", start_sec=1.0, end_sec=2.0), reason="Check ID")
        frame = ReplayFrame(EvidenceFrame(id="ambiguous_frame", timestamp_sec=1.0, source_ref="synthetic.mov"),
                            np.zeros((32, 32, 3), np.uint8), b"jpg")
        class Model:
            def text(self, *args, **kwargs): return "One cashier is inspecting a passport."
            def entail(self, *args): return [[.99, .005, .005]]
        observer = TextObserver(Model(), video())
        with patch("backend.semantic.followup.sample_window", return_value=[frame]):
            answer, _ = observer.answer(question, graph)
        self.assertEqual(len(observer.records[0]["observations"]), 1)
        self.assertEqual(answer.actions, [])
        self.assertIn("grounded uniquely", observer.records[0]["abstention_reason"])

    def test_semantic_alignment_does_not_consume_visual_budget(self):
        class Semantics:
            calls = 0
            def candidates(self, graph): return [{"key": "some_claim"}]
            def run(self, graph, candidates):
                self.calls += 1
                return graph
        class Observer:
            calls = 0
            def answer(self, *args):
                self.calls += 1
                return VisualAnswer(status="not_visible", explanation="Unclear"), []
        q = EvidenceQuestion(id="q1", rule_id="CD12", matcher=EventMatcher(kind="event", action="physical_id_checked"),
                    window=TimeWindow(relation="during", start_sec=0.0, end_sec=2.0), reason="Check ID")
        observer, semantic = Observer(), Semantics()
        with patch("backend.followup.pipeline.plan_questions", return_value=[q, q.model_copy(update={"id": "q2"})]):
            result = refine(self.registry, self.graph, video(), None, max_calls=2, observer=observer, semantic_matcher=semantic)
        self.assertEqual(result.calls, 2)
        self.assertEqual(observer.calls, 2)
        self.assertEqual(result.semantic_calls, 1)
        self.assertEqual(semantic.calls, 1)

    def test_plain_model_disables_generated_json(self):
        with self.assertRaisesRegex(TypeError, "Generated JSON is disabled"):
            TextVLM.structured(None, "prompt", None)

    def test_speculative_id_description_cannot_be_upgraded_by_confident_semantic_score(self):
        question = EvidenceQuestion(id="weak_id", rule_id="CD12", matcher=EventMatcher(kind="event", action="physical_id_checked"),
                    window=TimeWindow(relation="during", start_sec=1.0, end_sec=2.0), reason="Check ID")
        frame = ReplayFrame(EvidenceFrame(id="weak_frame", timestamp_sec=1.0, source_ref="synthetic.mov"),
                            np.zeros((32, 32, 3), np.uint8), b"jpg")
        class Model:
            def text(self, *args, **kwargs):
                return "The man is holding a card, suggesting a transaction or verification process is underway."
            def entail(self, *args): return [[.999, .0005, .0005]]
        observer = TextObserver(Model(), video())
        with patch("backend.semantic.followup.sample_window", return_value=[frame]):
            answer, _ = observer.answer(question, self.graph)
        self.assertEqual(answer.actions, [])
        self.assertIn("speculates", observer.records[0]["abstention_reason"])


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


class PlainAnalyzerTests(unittest.TestCase):
    def test_optional_plain_text_failures_preserve_baseline_findings(self):
        class Model:
            name = "fake-prose"
            def entail(self, context, questions): return [[.01, .01, .98] for _ in questions]
        class Reconstructor:
            vlm = Model()
            def run(self, path):
                return reconstruct_captions(video(), [caption(0, 8, {})], CaptionConfig(), self.vlm.name)
        graph = timeline({"room_occupied": lambda t: True, "cashier_at_station": lambda t: t < 4,
                          "safe_open": lambda t: True, "at_safe": lambda t: t < 4})
        reconstructor = Reconstructor()
        baseline = refine(load_registry(), graph, video(), reconstructor.vlm, max_calls=0)
        with tempfile.TemporaryDirectory() as directory, \
             patch("backend.analyzers.questions.build_timeline", return_value=graph), \
             patch("backend.analyzers.questions.describe_windows", side_effect=RuntimeError("Caption failed")), \
             patch("backend.analyzers.questions.refine", side_effect=[RuntimeError("Follow-up failed"), baseline]) as refinement, \
             patch("backend.analyzers.questions.atomic_json", side_effect=OSError("Disk full")), \
             self.assertLogs("backend.analyzers.questions", level="ERROR"):
            analyzer = QuestionAnalyzer(reconstructor, timeline_dir=Path(directory))
            findings = analyzer.analyze(Path("synthetic.mov"))
        self.assertTrue(findings)
        self.assertEqual(len(findings), len(reportable(baseline.report, analyzer.policy)))
        self.assertEqual(refinement.call_args_list[0].args[-2], 2)
        self.assertEqual(refinement.call_args_list[1].args[-2], 0)

    def test_scene_grounding_uses_plain_model_text_without_a_json_schema(self):
        class Model:
            def text(self, prompt, images, **kwargs): return "[100, 200, 900, 800]"
            def structured(self, *args, **kwargs): raise AssertionError("Generated JSON is forbidden")
        self.assertEqual(ground(Model(), np.zeros((32, 32, 3), np.uint8), "the desk"), (.1, .2, .9, .8))

    def test_api_caption_path_never_requests_generated_json(self):
        class Model:
            name = "fake-prose"
            text_calls = 0
            def text(self, *args, **kwargs):
                self.text_calls += 1
                return "The cashier sits at the desk; other details are unclear."
            def entail(self, context, questions): return [[.01, .01, .98] for _ in questions]
            def structured(self, *args, **kwargs): raise AssertionError("JSON generation is forbidden")
        class Reconstructor:
            def __init__(self): self.vlm = Model()
            def run(self, path):
                return reconstruct_captions(video(), [caption(0, 8, {})], CaptionConfig(), self.vlm.name)
        reconstructor = Reconstructor()
        with tempfile.TemporaryDirectory() as directory:
            analyzer = QuestionAnalyzer(reconstructor, max_followup_calls=0, temporal_scan=True, timeline_dir=Path(directory))
            analyzer.analyze(Path("synthetic.mov"))
            self.assertEqual(reconstructor.vlm.text_calls, 1)
            self.assertTrue((Path(directory) / "synthetic.captions.json").exists())


class WindowsInputTests(unittest.TestCase):
    def test_utf8_label_names_ignore_windows_locale_and_accept_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_bytes(b'\xef\xbb\xbf' + '{"Х-3.mov": "no_violation"}'.encode("utf-8"))
            original = Path.read_text
            def windows_read(instance, *args, **kwargs):
                kwargs.setdefault("encoding", "cp1251")
                return original(instance, *args, **kwargs)
            with patch.object(Path, "read_text", windows_read):
                self.assertEqual(read_json(path), {"Х-3.mov": "no_violation"})
            output = Path(directory) / "output.json"
            write(output, {"Х-3.mov": "Сейф"})
            self.assertIn("Сейф", output.read_bytes().decode("utf-8"))

    def test_latin_prefix_and_uppercase_extension_resolve_to_canonical_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "X-3.MOV"
            path.touch()
            self.assertEqual(resolve_videos(Path(directory), {"Х-3.mov": "no_violation"}), {"Х-3.mov": path})

    def test_missing_or_ambiguous_inputs_fail_without_skipping_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "Missing 1 labelled videos"):
                resolve_videos(root, {"Х-3.mov": "no_violation"})
            (root / "X-3.mov").touch()
            (root / "x_03.mp4").touch()
            with self.assertRaisesRegex(ValueError, "Ambiguous video"):
                resolve_videos(root, {"Х-3.mov": "no_violation"})


if __name__ == "__main__":
    unittest.main()

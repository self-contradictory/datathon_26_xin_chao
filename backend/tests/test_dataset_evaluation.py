import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import httpx
import numpy as np

from backend.reconstruction.decode import Observation
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, decode_tracks
from backend.reconstruction.probes import PROBES
from backend.reconstruction.temporal import CashAction, CashActions, _merge_action, observe_cash_provenance
from backend.reconstruction.video import DecodedVideo
from backend.rules.engine import evaluate
from backend.rules.registry import load_registry
from backend.db.sqlite import SqliteDatabase
from backend.repositories.api_keys import SqliteApiKeyRepository
from backend.services.api_keys import ApiKeyService

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "eval"))
from batch_api import DEFAULT_API_KEY, run_video
from score_api import load_expected, score, write_json


def fixture(*, cash=False, eating=False):
    _, jpeg = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    video = DecodedVideo(Path("heldout.mov"), 20.0, 1.0, 32, 32, 1.0,
                         np.arange(20, dtype=float), list(range(20)), [jpeg.tobytes()] * 20)
    true = {"cashier_seated", "cashier_at_station", "room_occupied"}
    if cash:
        true.add("cash_on_desk")
    if eating:
        true.add("eating")
    tracks = {probe.key: AttributeTrack(probe, [Observation(float(t), .999 if probe.key in true else .001)
                                                for t in video.times]) for probe in PROBES}
    decode_tracks(video, tracks)
    return video, build_timeline(Reconstruction(video, tracks, "synthetic-test"))


def action(*, kind="rejected_banknotes_recombined", origins=True, status="observed", start=4, end=6):
    return CashAction(action=kind, first_frame_id=f"f_{start}", last_frame_id=f"f_{end}",
                      evidence_frame_ids=[f"f_{start}", f"f_{end}"], origins_visible=origins,
                      status=status, explanation="Synthetic origin and recombination evidence")


class RuleCoverageTests(unittest.TestCase):
    def test_all_source_labels_and_aspects_are_accounted_for(self):
        expected = load_expected()
        catalog = json.loads((BACKEND / "eval/dataset_labels.json").read_text(encoding="utf-8"))
        self.assertEqual(len(expected), 42)
        self.assertEqual(sum(v == "violation" for v in expected.values()), 22)
        self.assertEqual({item["video"]: item["expected"] for item in catalog["videos"]}, expected)
        registered = {rule.rule_id for rule in load_registry().rules}
        for item in catalog["videos"]:
            self.assertEqual(bool(item["aspects"]), item["expected"] == "violation")
            for aspect in item["aspects"]:
                self.assertTrue(set(aspect["any_of_rules"]) <= registered)
        labels = {item["video"]: item for item in catalog["videos"]}
        self.assertEqual(labels["Х-47.mov"]["timestamp_sec"], 68)
        self.assertEqual(labels["Х-46.mov"]["aspects"][0]["any_of_rules"], ["CD15-EATING-WITH-CASH-EXPOSED"])
        self.assertEqual(labels["Х-13.mov"]["aspects"][1]["observability"], "external_only")

    def test_food_alone_is_not_the_x46_rule(self):
        for cash, expected in [(False, "CLEAR"), (True, "VIOLATION")]:
            _, graph = fixture(cash=cash, eating=True)
            findings = [f for f in evaluate(load_registry(), graph, "shadow").findings()
                        if f.rule_id == "CD15-EATING-WITH-CASH-EXPOSED"]
            self.assertEqual([f.outcome for f in findings], [expected])

    def test_observed_rejection_and_separate_origins_are_distinct_rules(self):
        for kind, rule in [("rejected_banknotes_recombined", "CD18"), ("different_customer_cash_mixed", "CD19")]:
            _, graph = fixture()
            _merge_action(graph, action(kind=kind), {f"f_{i}" for i in range(20)}, 0, 12)
            findings = [f for f in evaluate(load_registry(), graph, "shadow").findings("VIOLATION")
                        if f.rule_id.startswith(("CD18", "CD19"))]
            self.assertEqual(len(findings), 1)
            self.assertTrue(findings[0].rule_id.startswith(rule))

    def test_unknown_origins_never_become_confirmed(self):
        _, graph = fixture()
        _merge_action(graph, action(origins=False), {f"f_{i}" for i in range(20)}, 0, 12)
        findings = [f for f in evaluate(load_registry(), graph, "shadow").findings()
                    if f.rule_id.startswith("CD18")]
        self.assertEqual([(f.outcome, f.unknown_kind) for f in findings], [("UNKNOWN", "weak_evidence")])

    def test_missing_laptop_use_does_not_prove_missing_accounting(self):
        _, graph = fixture(cash=True)
        report = evaluate(load_registry(), graph, "shadow")
        self.assertFalse([f for f in report.findings() if f.rule_id.startswith("CD20")])

    def test_accounting_claim_from_a_vlm_requires_external_confirmation(self):
        _, graph = fixture()
        _merge_action(graph, action(), {f"f_{i}" for i in range(20)}, 0, 12)
        event = graph.events[-1]
        event.action = "cash_operation_not_recorded"
        for verification, expected in [("replayed", "UNKNOWN"), ("human_confirmed", "VIOLATION")]:
            event.verification_status = verification
            findings = [f for f in evaluate(load_registry(), graph, "shadow").findings()
                        if f.rule_id.startswith("CD20")]
            self.assertEqual([f.outcome for f in findings], [expected])

    def test_temporal_frames_must_exist_and_support_action_endpoints(self):
        _, graph = fixture()
        before = len(graph.events)
        for candidate in [action(start=30), action().model_copy(update={"evidence_frame_ids": ["f_1", "f_2"]})]:
            with self.assertRaises(ValueError):
                _merge_action(graph, candidate, {f"f_{i}" for i in range(20)}, 0, 12)
        self.assertEqual(len(graph.events), before)

    def test_overlapping_windows_do_not_duplicate_an_action(self):
        _, graph = fixture()
        allowed = {f"f_{i}" for i in range(20)}
        _merge_action(graph, action(), allowed, 0, 12)
        _merge_action(graph, action(start=6, end=8), allowed, 6, 18)
        events = [event for event in graph.events if event.action == "rejected_banknotes_recombined"]
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].time.start_sec, events[0].time.end_sec), (4, 8))
        type(graph).model_validate(graph.model_dump(mode="json"))

    def test_scanner_uses_frames_without_expected_labels_or_video_names(self):
        video, graph = fixture()

        class EmptyModel:
            calls = 0

            def structured(inner, prompt, schema, images, **kwargs):
                inner.calls += 1
                self.assertNotIn("heldout.mov", prompt)
                self.assertNotIn("expected", prompt)
                self.assertNotIn("Х-44", prompt)
                self.assertLessEqual(len(images), 8)
                return CashActions()

        model = EmptyModel()
        result = observe_cash_provenance(graph, video, model)
        self.assertEqual((result.calls, model.calls, result.errors), (3, 3, []))


class APIBatchTests(unittest.TestCase):
    def test_documented_batch_key_can_be_registered_and_authenticated(self):
        with tempfile.TemporaryDirectory() as directory:
            database = SqliteDatabase(Path(directory) / "app.db")
            database.initialize()
            service = ApiKeyService(SqliteApiKeyRepository(database))
            service.sync({"mac": DEFAULT_API_KEY})
            authenticated = service.authenticate(DEFAULT_API_KEY)
            self.assertIsNotNone(authenticated)
            self.assertEqual(authenticated.name, "mac")
            self.assertIsNone(service.authenticate("local-test-key"))

    def test_upload_poll_resume_and_no_label_in_request(self):
        counts = {"uploads": 0, "polls": 0}

        def handler(request):
            if request.method == "POST":
                counts["uploads"] += 1
                body = request.read()
                self.assertIn(b"simulated video", body)
                self.assertNotIn(b"no_violation", body)
                self.assertNotIn(b"expected", body)
                return httpx.Response(200, json={"job_id": "job1"})
            counts["polls"] += 1
            return httpx.Response(200, json={"job_id": "job1", "status": "processing" if counts["polls"] == 1 else "done",
                                             "verdict": None if counts["polls"] == 1 else "violation", "violations": []})

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            video = Path(directory) / "Х-46.mov"
            video.write_bytes(b"simulated video")
            destination = Path(directory) / "result.json"
            with httpx.Client(base_url="http://test/api/v1/", transport=httpx.MockTransport(handler)) as client:
                run_video(client, video, destination, 0)
                run_video(client, video, destination, 0)
            self.assertEqual(counts, {"uploads": 1, "polls": 2})
            self.assertEqual(json.loads(destination.read_text())["verdict"], "violation")

    def test_network_interruption_preserves_job_id_for_resume(self):
        counts = {"uploads": 0, "polls": 0}

        def handler(request):
            if request.method == "POST":
                counts["uploads"] += 1
                return httpx.Response(200, json={"job_id": "existing-job"})
            counts["polls"] += 1
            if counts["polls"] == 1:
                raise httpx.ConnectError("interrupted", request=request)
            return httpx.Response(200, json={"job_id": "existing-job", "status": "done", "verdict": "no_violation"})

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            video = Path(directory) / "clip.mov"
            video.write_bytes(b"video")
            destination = Path(directory) / "result.json"
            with httpx.Client(base_url="http://test/api/v1/", transport=httpx.MockTransport(handler)) as client:
                run_video(client, video, destination, 0)
                self.assertEqual(json.loads(destination.read_text())["status"], "client_error")
                run_video(client, video, destination, 0)
            self.assertEqual(counts["uploads"], 1)

    def test_failed_jobs_are_not_clean_and_require_explicit_retry(self):
        uploads = []

        def handler(request):
            if request.method == "POST":
                uploads.append(1)
                return httpx.Response(200, json={"job_id": "failed-job"})
            return httpx.Response(200, json={"job_id": "failed-job", "status": "failed", "verdict": None})

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            video = Path(directory) / "clip.mov"
            video.write_bytes(b"video")
            destination = Path(directory) / "result.json"
            with httpx.Client(base_url="http://test/api/v1/", transport=httpx.MockTransport(handler)) as client:
                run_video(client, video, destination, 0)
                run_video(client, video, destination, 0)
                self.assertEqual(len(uploads), 1)
                run_video(client, video, destination, 0, retry_failed=True)
                self.assertEqual(len(uploads), 2)
            self.assertIsNone(json.loads(destination.read_text())["verdict"])

    def test_confusion_matrix_failures_and_missing_cases(self):
        expected = {"tp.mov": "violation", "tn.mov": "no_violation", "fp.mov": "no_violation",
                    "fn.mov": "violation", "failed.mov": "violation", "missing.mov": "no_violation",
                    "invalid.mov": "violation"}
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            out = Path(directory)
            for name, predicted in [("tp.mov", "violation"), ("tn.mov", "no_violation"),
                                    ("fp.mov", "violation"), ("fn.mov", "no_violation")]:
                write_json(out / f"{name}.json", {"status": "done", "verdict": predicted, "violations": []})
            write_json(out / "failed.mov.json", {"status": "failed", "verdict": None})
            (out / "invalid.mov.json").write_text("[]", encoding="utf-8-sig")
            result = score(out, expected)
            self.assertEqual([result[key] for key in ("true_positives", "true_negatives", "false_positives", "false_negatives")], [1, 1, 1, 1])
            self.assertEqual((result["completed"], result["failed"], result["remaining"]), (4, 2, 1))
            self.assertEqual(result["accuracy"], .5)
            self.assertAlmostEqual(result["correct_over_all"], 2 / 7)
            self.assertEqual(result["mismatches"], ["fp.mov", "fn.mov"])


if __name__ == "__main__":
    unittest.main()

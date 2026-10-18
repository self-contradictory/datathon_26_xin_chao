import unittest
from pathlib import Path

import cv2
import numpy as np

from backend.reconstruction.decode import Observation
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, decode_tracks
from backend.reconstruction.probes import PROBES
from backend.reconstruction.video import DecodedVideo
from backend.rules.engine import evaluate
from backend.rules.registry import load_registry
from backend.rules.verdict import ReportingPolicy, reportable, to_violations

PHONE_RULE = "CD25-MOBILE-PHONE-IN-CASH-ROOM"


def graph(*true: str):
    _, jpeg = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    video = DecodedVideo(Path("general.mov"), 20.0, 1.0, 32, 32, 1.0,
                         np.arange(20, dtype=float), list(range(20)), [jpeg.tobytes()] * 20)
    present = {"cashier_seated", "cashier_at_station", "room_occupied", *true}
    tracks = {}
    for probe in PROBES:
        values = [.999 if probe.key in present and (probe.key != "phone" or 6 <= t <= 12) else .001
                  for t in video.times]
        tracks[probe.key] = AttributeTrack(probe, [Observation(float(t), p) for t, p in zip(video.times, values)])
    decode_tracks(video, tracks)
    return build_timeline(Reconstruction(video, tracks, "synthetic-test"))


class GeneralRuleTests(unittest.TestCase):
    def test_phone_use_is_reported_with_its_clause(self):
        report = evaluate(load_registry(), graph("phone"), "shadow")
        findings = [f for f in report.findings("VIOLATION") if f.rule_id == PHONE_RULE]
        self.assertEqual(len(findings), 1)
        self.assertAlmostEqual(findings[0].timecode_sec, 6.0, delta=1.0)
        violations = to_violations(reportable(report, ReportingPolicy(production_only=False)), lambda _: b"jpeg")
        phone = [v for v in violations if "п. 12" in v.description and "phone" in v.type]
        self.assertEqual(len(phone), 1)
        self.assertEqual(phone[0].rule_id, PHONE_RULE)
        self.assertEqual(phone[0].source, findings[0].source)
        self.assertEqual(phone[0].model_dump()["source"]["url"],
                         "https://adilet.zan.kz/rus/docs/V1900019680")

    def test_no_phone_no_finding(self):
        report = evaluate(load_registry(), graph(), "shadow")
        self.assertFalse([f for f in report.findings("VIOLATION", "UNKNOWN") if f.rule_id == PHONE_RULE])

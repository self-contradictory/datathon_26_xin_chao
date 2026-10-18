import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

from backend.perception.features import FeatureConfig, deduplicate, in_room
from backend.perception.fusion import FusionConfig, fuse
from backend.perception.pose import Person
from backend.perception.scene import Scene
from backend.reconstruction.decode import Observation
from backend.reconstruction.graph import build_timeline
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, decode_tracks
from backend.reconstruction.probes import PERCEPTION_PROBES
from backend.reconstruction.video import DecodedVideo
from backend.rules.engine import evaluate
from backend.rules.registry import load_registry

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "eval" / "tuning"))
from calibrate import otsu


def timeline(states):
    """states maps a probe key to a function of time returning True/False; others are False."""
    _, jpeg = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    times = np.arange(0.0, 12.0, 0.5)
    video = DecodedVideo(Path("synthetic.mov"), 12.0, 2.0, 32, 32, 2.0, times, list(range(len(times))),
                         [jpeg.tobytes()] * len(times))
    tracks = {probe.key: AttributeTrack(probe, [
        Observation(float(t), .999 if states.get(probe.key, lambda _: False)(t) else .001) for t in times
    ]) for probe in PERCEPTION_PROBES}
    decode_tracks(video, tracks)
    return build_timeline(Reconstruction(video, tracks, "synthetic-test"))


def outcomes(graph, rule):
    return [f.outcome for f in evaluate(load_registry(), graph, "shadow").findings() if f.rule_id.startswith(rule)]


def person(box, score=0.99):
    return Person(box, score, np.zeros((17, 3), dtype=np.float32))


SCENE = Scene({"desk": (0.1, 0.45, 0.65, 0.65), "safe": (0.6, 0.3, 0.8, 0.5), "laptop": (0.45, 0.4, 0.6, 0.5),
               "machine": (0.1, 0.4, 0.3, 0.5), "door_handle": (0.2, 0.33, 0.24, 0.37)})


class LeftOpenTests(unittest.TestCase):
    present = {"room_occupied": lambda t: True, "cashier_seated": lambda t: True,
               "cashier_at_station": lambda t: True}

    def test_safe_open_after_the_cashier_walks_away(self):
        graph = timeline(self.present | {"safe_open": lambda t: True, "at_safe": lambda t: t < 4})
        self.assertIn("VIOLATION", outcomes(graph, "CD05B"))

    def test_safe_closed_or_in_use_is_not_left_open(self):
        for states in ({"safe_open": lambda t: False, "at_safe": lambda t: t < 4},
                       {"safe_open": lambda t: True, "at_safe": lambda t: True},
                       {"safe_open": lambda t: True, "at_safe": lambda t: t < 10}):
            self.assertNotIn("VIOLATION", outcomes(timeline(self.present | states), "CD05B"))

    def test_door_left_open_after_someone_passes(self):
        graph = timeline(self.present | {"door_open": lambda t: t > 2, "person_in_doorway": lambda t: 2 < t < 4})
        self.assertIn("VIOLATION", outcomes(graph, "CD09B"))
        closed = timeline(self.present | {"door_open": lambda t: 2 < t < 4, "person_in_doorway": lambda t: 2 < t < 4})
        self.assertNotIn("VIOLATION", outcomes(closed, "CD09B"))

    def test_lock_screen_is_not_an_unlocked_computer(self):
        away = {"room_occupied": lambda t: t < 4, "cashier_at_station": lambda t: t < 4, "screen_on": lambda t: True}
        self.assertNotIn("VIOLATION", outcomes(timeline(away), "CD07"))
        self.assertIn("VIOLATION", outcomes(timeline(away | {"screen_unlocked": lambda t: True}), "CD07"))


class PersonSignalTests(unittest.TestCase):
    def test_people_behind_the_glass_are_not_in_the_room(self):
        config = FeatureConfig()
        self.assertFalse(in_room(person((0.0, 0.26, 0.11, 0.35)), SCENE, config))
        self.assertTrue(in_room(person((0.3, 0.34, 0.47, 0.48)), SCENE, config))
        self.assertTrue(in_room(person((0.05, 0.2, 0.25, 0.44)), SCENE, config))

    def test_upper_and_whole_body_boxes_count_once(self):
        people = [person((0.22, 0.34, 0.43, 0.48)), person((0.23, 0.35, 0.44, 0.61), 0.8),
                  person((0.6, 0.4, 0.8, 0.7))]
        self.assertEqual(len(deduplicate(people)), 2)


class CalibrationTests(unittest.TestCase):
    def test_bias_moves_the_decision_point(self):
        grid = np.arange(4.0)
        base = {"eating": np.array([0.001, 0.002, 0.05, 0.08])}
        raw = fuse(grid, base, {}, None, ["eating"])["eating"]
        shifted = fuse(grid, base, {}, None, ["eating"], FusionConfig(base_bias={"eating": -4.0}))["eating"]
        self.assertTrue((raw < 0.5).all())
        self.assertEqual((shifted > 0.5).tolist(), [False, False, True, True])

    def test_otsu_splits_two_modes(self):
        values = np.concatenate([np.random.default_rng(0).normal(-7, 0.5, 200),
                                 np.random.default_rng(1).normal(-2, 0.5, 50)])
        threshold, _ = otsu(values)
        self.assertTrue(-6 < threshold < -3)


if __name__ == "__main__":
    unittest.main()

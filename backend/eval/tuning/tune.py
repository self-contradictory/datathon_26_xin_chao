"""Coordinate-descent tuning of perception parameters, with leave-one-video-out validation.

Each evaluated setting is memoized as a per-video correctness vector, so the leave-one-out runs
(one full descent per held-out video, selecting only on the other videos) reuse most work.
The held-out accuracy is the honest number; in-sample accuracy is optimistic.
"""
import copy
import json
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from backend.perception.pipeline import PerceptionConfig
from common import CACHE, expected, write_json
from fused_bench import Experiment, run


@dataclass(frozen=True)
class Knob:
    name: str
    values: tuple
    apply: Callable[[PerceptionConfig, object], None]
    default: object = None

    @property
    def start(self):
        return self.default if self.default is not None else self.values[len(self.values) // 2]


def offset(key: str, values=(-2.0, -1.0, 0.0, 1.0, 2.0)) -> Knob:
    return Knob(f"offset:{key}", values, lambda c, v, key=key: c.fusion.offsets.__setitem__(key, v), 0.0)


def dwell(key: str, values, default) -> Knob:
    return Knob(f"dwell:{key}", values, lambda c, v, key=key: c.dwell.__setitem__(key, v), default)


def module(name: str, target, attribute: str, values, default) -> Knob:
    """A module-level constant (for example graph.KNOWN_CONFIDENCE), set before each evaluation."""
    return Knob(name, values, lambda c, v: setattr(target, attribute, v), default)


def feature(name: str, values, default) -> Knob:
    return Knob(f"feature:{name}", values, lambda c, v: setattr(c.features, name, v), default)


class Tuner:
    def __init__(self, base: Experiment, knobs: list[Knob]) -> None:
        self.base, self.knobs = base, knobs
        self.videos = list(expected())
        self.memo: dict[tuple, np.ndarray] = {}

    def config(self, state: dict[str, object]) -> PerceptionConfig:
        config = copy.deepcopy(self.base.config)
        for knob in self.knobs:
            knob.apply(config, state.get(knob.name, knob.start))
        return config

    def correct(self, state: dict[str, object]) -> np.ndarray:
        key = tuple(sorted(state.items()))
        if key not in self.memo:
            experiment = Experiment("tune", self.base.base, self.base.regions, self.config(state), self.base.registry)
            rows = {row["video"]: row["correct"] for row in run(experiment, verbose=False, save=False)["rows"]}
            self.memo[key] = np.array([rows.get(video, False) for video in self.videos], float)
        return self.memo[key]

    def descend(self, mask: np.ndarray, rounds: int = 2) -> dict[str, object]:
        state: dict[str, object] = {}
        for _ in range(rounds):
            changed = False
            for knob in self.knobs:
                current = state.get(knob.name, knob.start)
                best, best_score = current, self.correct(state | {knob.name: current})[mask].sum()
                for value in knob.values:
                    score = self.correct(state | {knob.name: value})[mask].sum()
                    if score > best_score + 1e-9:
                        best, best_score = value, score
                if state.get(knob.name) != best:
                    changed = True
                state[knob.name] = best
            if not changed:
                break
        return state

    def folds(self, count: int) -> list[np.ndarray]:
        """Stratified folds: violation and no-violation videos dealt round-robin."""
        labels = expected()
        order = [i for i, v in enumerate(self.videos) if labels[v] == "violation"]
        order += [i for i, v in enumerate(self.videos) if labels[v] != "violation"]
        assignment = np.empty(len(self.videos), int)
        for position, index in enumerate(order):
            assignment[index] = position % count
        return [assignment == fold for fold in range(count)]

    def validate(self, folds: int = 7, rounds: int = 2) -> dict:
        everything = np.ones(len(self.videos), bool)
        state = self.descend(everything, rounds)
        in_sample = self.correct(state)
        held_out = np.zeros(len(self.videos))
        for test in self.folds(folds):
            held_out[test] = self.correct(self.descend(~test, rounds))[test]
        return {"state": state, "in_sample_correct": int(in_sample.sum()),
                "held_out_correct": int(held_out.sum()), "videos": len(self.videos), "folds": folds,
                "held_out": dict(zip(self.videos, map(bool, held_out))), "evaluations": len(self.memo)}


def save(name: str, result: dict) -> None:
    write_json(CACHE / "results" / f"tune-{name}.json", json.loads(json.dumps(result, default=str)))

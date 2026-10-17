from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Observation:
    time: float
    probability: float


@dataclass(frozen=True, slots=True)
class Segment:
    first: int
    last: int
    value: bool
    confidence: float
    start: float = 0.0
    end: float = 0.0


def decode_binary(
    probabilities: np.ndarray, switches: np.ndarray, prior: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    count = len(probabilities)
    p = np.clip(probabilities, 0.0001, 1 - 0.0001)
    emission = np.stack([np.log(1 - p), np.log(p)], axis=1)
    log_prior = np.log(np.array([1 - prior, prior]))
    transitions = [np.log(np.array([[1 - s, s], [s, 1 - s]])) for s in switches]
    score = log_prior + emission[0]
    back = np.zeros((count, 2), int)
    for t in range(1, count):
        candidates = score[:, None] + transitions[t - 1]
        back[t] = candidates.argmax(axis=0)
        score = candidates.max(axis=0) + emission[t]
    states = np.zeros(count, int)
    states[-1] = int(score.argmax())
    for t in range(count - 1, 0, -1):
        states[t - 1] = back[t, states[t]]
    forward = np.zeros((count, 2))
    forward[0] = log_prior + emission[0]
    for t in range(1, count):
        forward[t] = np.logaddexp.reduce(
            forward[t - 1][:, None] + transitions[t - 1], axis=0
        ) + emission[t]
    backward = np.zeros((count, 2))
    for t in range(count - 2, -1, -1):
        backward[t] = np.logaddexp.reduce(
            transitions[t] + (emission[t + 1] + backward[t + 1])[None, :], axis=1
        )
    joint = forward + backward
    posterior = np.exp(joint[:, 1] - np.logaddexp(joint[:, 0], joint[:, 1]))
    return states, posterior


def segments(states: np.ndarray, posterior: np.ndarray) -> list[Segment]:
    result: list[Segment] = []
    first = 0
    for t in range(1, len(states) + 1):
        if t == len(states) or states[t] != states[first]:
            value = bool(states[first])
            support = posterior[first:t] if value else 1 - posterior[first:t]
            result.append(Segment(first, t - 1, value, float(support.mean())))
            first = t
    return result


def switch_probabilities(times: np.ndarray, dwell: float) -> np.ndarray:
    return np.clip(1 - np.exp(-np.diff(times) / dwell), 1e-4, 0.5)

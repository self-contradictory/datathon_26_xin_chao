"""People and body keypoints from torchvision's COCO Keypoint R-CNN (BSD licensed, no extra dependency)."""
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision.models.detection import KeypointRCNN_ResNet50_FPN_Weights, keypointrcnn_resnet50_fpn

# COCO keypoint order.
NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 0, 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE = 11, 12, 13, 14, 15, 16


@dataclass(slots=True)
class Person:
    box: tuple[float, float, float, float]
    score: float
    keypoints: np.ndarray
    track: int = -1

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def center(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2

    def point(self, *indices: int, min_score: float = 0.3) -> tuple[float, float] | None:
        visible = [self.keypoints[i, :2] for i in indices if self.keypoints[i, 2] >= min_score]
        return tuple(np.mean(visible, axis=0)) if visible else None

    def to_json(self) -> dict:
        return {"box": [round(v, 4) for v in self.box], "score": round(self.score, 3),
                "keypoints": np.round(self.keypoints, 4).tolist(), "track": self.track}

    @classmethod
    def from_json(cls, data: dict) -> Person:
        return cls(tuple(data["box"]), data["score"], np.asarray(data["keypoints"], dtype=np.float32),
                   data.get("track", -1))


@dataclass(slots=True)
class PoseSequence:
    times: np.ndarray
    people: list[list[Person]] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"times": self.times.tolist(), "people": [[p.to_json() for p in frame] for frame in self.people]}

    @classmethod
    def from_json(cls, data: dict) -> PoseSequence:
        return cls(np.asarray(data["times"]), [[Person.from_json(p) for p in frame] for frame in data["people"]])


class PoseEstimator:
    def __init__(self, device: str | None = None, threshold: float = 0.5, min_size: int = 640) -> None:
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.threshold = threshold
        self._model = keypointrcnn_resnet50_fpn(
            weights=KeypointRCNN_ResNet50_FPN_Weights.COCO_V1, min_size=min_size, max_size=1333,
        ).eval().to(self.device)

    @torch.inference_mode()
    def __call__(self, images: list[np.ndarray]) -> list[list[Person]]:
        batch = [torch.from_numpy(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float().div(255)
                 .to(self.device) for image in images]
        results = []
        for image, output in zip(images, self._model(batch), strict=True):
            h, w = image.shape[:2]
            scale = np.array([w, h, w, h], dtype=np.float32)
            people = []
            for box, score, keypoints, kscores in zip(
                output["boxes"].cpu().numpy(), output["scores"].cpu().numpy(),
                output["keypoints"].cpu().numpy(), output["keypoints_scores"].cpu().numpy(), strict=True,
            ):
                if score < self.threshold:
                    continue
                points = np.column_stack([keypoints[:, 0] / w, keypoints[:, 1] / h,
                                          1 / (1 + np.exp(-kscores))]).astype(np.float32)
                people.append(Person(tuple(float(v) for v in box / scale), float(score), points))
            results.append(people)
        return results


def detect_people(path: Path, estimator: PoseEstimator, fps: float = 4.0, batch: int = 4) -> PoseSequence:
    capture = cv2.VideoCapture(str(path))
    native = capture.get(cv2.CAP_PROP_FPS) or 30.0
    times, people, pending = [], [], []
    next_sample, index = 0.0, 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            moment = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if moment == 0.0 and index > 0:
                moment = index / native
            if moment + 1e-6 >= next_sample:
                times.append(moment)
                pending.append(frame)
                next_sample += 1.0 / fps
                if len(pending) == batch:
                    people.extend(estimator(pending))
                    pending = []
            index += 1
    finally:
        capture.release()
    if pending:
        people.extend(estimator(pending))
    return PoseSequence(np.asarray(times), people)

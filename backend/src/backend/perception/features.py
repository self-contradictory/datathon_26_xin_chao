"""Per-time scene signals from body keypoints, local patch motion and the grounded layout.

Every signal is a probability-like score in [0, 1] sampled on the pose timeline. They feed the
same binary HMM as the VLM probes, so a signal only needs to rank frames correctly.
"""
from dataclasses import dataclass, field

import numpy as np

from backend.perception.motion import PatchMotion
from backend.perception.pose import (
    L_ANKLE, L_HIP, L_SHOULDER, L_WRIST, NOSE, R_ANKLE, R_HIP, R_SHOULDER, R_WRIST, Person, PoseSequence,
)
from backend.perception.scene import Box, Scene, expand


@dataclass(slots=True)
class FeatureConfig:
    min_score: float = 0.7
    floor_margin: float = 0.0
    tall: float = 0.2
    door_width: float = 0.22
    door_up: float = 0.20
    door_down: float = 0.12
    door_speed: float = 0.0
    safe_reach: float = 0.15
    safe_floor: float = 0.15
    transit_speed: float = 0.08
    door_transit_speed: float = 0.03
    hand_mouth: float = 0.045
    hand_gap: float = 0.05
    door_change: float = 15.5
    door_change_scale: float = 2.0
    lights_ratio: float = 0.7


@dataclass(slots=True)
class Signals:
    times: np.ndarray
    values: dict[str, np.ndarray] = field(default_factory=dict)
    people: list[list[Person]] = field(default_factory=list)

    def at(self, key: str, times: np.ndarray, reduce: str = "mean", window: float = 0.5) -> np.ndarray:
        """Resample a signal onto other sample times by reducing over +-window seconds."""
        values = self.values[key]
        out = np.empty(len(times))
        for index, moment in enumerate(times):
            inside = np.abs(self.times - moment) <= window + 1e-6
            chosen = values[inside] if inside.any() else values[[int(np.argmin(np.abs(self.times - moment)))]]
            out[index] = chosen.max() if reduce == "max" else chosen.mean()
        return out


def _inside(point: tuple[float, float] | None, box: Box) -> bool:
    return point is not None and box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _overlap(a: Box, b: Box) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (b[2] - b[0]) * (b[3] - b[1])
    return w * h / area if area > 0 else 0.0


def _iou(a: Box, b: Box) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - w * h
    return w * h / union if union > 0 else 0.0


def deduplicate(people: list[Person], containment: float = 0.75) -> list[Person]:
    """Keypoint R-CNN sometimes returns a second box for one body (upper body vs whole body);
    drop a box when most of the smaller one lies inside a higher-scoring one."""
    kept: list[Person] = []
    for person in sorted(people, key=lambda p: -p.score):
        if all(_overlap(person.box, other.box) < containment and _overlap(other.box, person.box) < containment
               for other in kept):
            kept.append(person)
    return kept


def speeds(frames: list[list[Person]], times: np.ndarray) -> list[list[float]]:
    """Box-centre speed (frame widths/heights per second) of each person, matched to the most
    overlapping box in the neighbouring samples. Unmatched people get speed 0."""
    result = []
    for index, people in enumerate(frames):
        row = []
        for person in people:
            moves = []
            for other in (index - 1, index + 1):
                if not 0 <= other < len(frames) or not frames[other]:
                    continue
                match = max(frames[other], key=lambda q: _iou(q.box, person.box))
                if _iou(match.box, person.box) < 0.2:
                    continue
                (x0, y0), (x1, y1) = person.center, match.center
                moves.append(np.hypot(x1 - x0, y1 - y0) / max(1e-3, abs(times[other] - times[index])))
            row.append(float(np.mean(moves)) if moves else 0.0)
        result.append(row)
    return result


def link_tracks(frames: list[list[Person]], min_iou: float = 0.3, patience: int = 3) -> list[list[int]]:
    """Greedy IoU association; a track survives up to `patience` samples without a detection."""
    ids, alive, next_id = [], [], 0  # alive: [box, track id, samples since last seen]
    for people in frames:
        row, taken = [], set()
        for person in people:
            best = max(((i, _iou(person.box, box)) for i, (box, _, _) in enumerate(alive) if i not in taken),
                       key=lambda item: item[1], default=(None, 0.0))
            if best[0] is not None and best[1] >= min_iou:
                taken.add(best[0])
                row.append(alive[best[0]][1])
            else:
                row.append(next_id)
                next_id += 1
        seen = {track for track in row}
        alive = [[box, track, 0] for box, track in zip((p.box for p in people), row, strict=True)] + [
            [box, track, missed + 1] for box, track, missed in alive if track not in seen and missed + 1 <= patience]
        ids.append(row)
    return ids


def outside_static(frames: list[list[Person]], times: np.ndarray, zone: Box, speed: float = 0.05,
                   min_seconds: float = 1.0) -> set[int]:
    """Track ids of people who stay in the door zone and never move: someone sitting behind the
    glass next to the door, not a person who came in."""
    ids = link_tracks(frames)
    moves = speeds(frames, times)
    stats: dict[int, list] = {}
    for moment, people, row, motion in zip(times, frames, ids, moves, strict=True):
        for person, track, velocity in zip(people, row, motion, strict=True):
            entry = stats.setdefault(track, [moment, moment, True, 0.0])
            entry[1] = moment
            entry[2] = entry[2] and _inside(person.center, zone)
            entry[3] = max(entry[3], velocity)
    return {track for track, (first, last, in_zone, fastest) in stats.items()
            if in_zone and fastest < speed and last - first >= min_seconds}


def door_zone(scene: Scene, config: FeatureConfig | None = None) -> Box:
    config = config or FeatureConfig()
    hx0, hy0, hx1, hy1 = scene.boxes["door_handle"]
    hx, hy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
    w, up, down = config.door_width, config.door_up, config.door_down
    return (hx - w, hy - up, hx + 0.35 * w, hy + down)


def in_room(person: Person, scene: Scene, config: FeatureConfig) -> bool:
    """People behind the glass wall end above the desk's top edge in the image; anyone in the
    room reaches down to it, unless they stand tall close to the camera."""
    if person.score < config.min_score:
        return False
    return person.box[3] >= scene.boxes["desk"][1] - config.floor_margin or person.height >= config.tall


def compute_signals(scene: Scene, pose: PoseSequence, motion: PatchMotion,
                    config: FeatureConfig = FeatureConfig(), aspect: float = 848 / 464) -> Signals:
    """aspect is frame height / width; keypoint distances are measured in frame heights."""
    regions = scene.regions
    desk, safe, door, laptop = scene.boxes["desk"], scene.boxes["safe"], regions["door"], scene.boxes["laptop"]
    zone = door_zone(scene, config)
    # Hands working the safe are at door height; hands resting on the desk just below it are not.
    reach = expand(safe, config.safe_reach, config.safe_reach, config.safe_reach, -config.safe_floor)
    station = expand(desk, 0.05, 0.6, 0.05, 0.5)
    count, settled, occupied, doorway_person, at_safe, at_laptop = [], [], [], [], [], []
    hands_desk, hand_mouth, near_count, far_count, at_station, hands_close = [], [], [], [], [], []
    people_in_room = [deduplicate([p for p in people if in_room(p, scene, config)]) for people in pose.people]
    static = outside_static(people_in_room, pose.times, zone)
    if static:
        ids = link_tracks(people_in_room)
        people_in_room = [[p for p, track in zip(people, row, strict=True) if track not in static]
                          for people, row in zip(people_in_room, ids, strict=True)]
    motion_speed = speeds(people_in_room, pose.times)
    for inside, moving in zip(people_in_room, motion_speed, strict=True):
        count.append(len(inside))
        occupied.append(max((p.score for p in inside), default=0.0))
        at_door = [_inside(p.center, zone) for p in inside]
        doorway_person.append(float(any(door and speed >= config.door_speed
                                        for door, speed in zip(at_door, moving, strict=True))))
        settled.append(sum(speed < (config.door_transit_speed if door else config.transit_speed)
                           for door, speed in zip(at_door, moving, strict=True)))
        wrists = [p.point(i) for p in inside for i in (L_WRIST, R_WRIST)]
        at_safe.append(float(any(_inside(w, reach) for w in wrists)
                             or any(_overlap(p.box, safe) > 0.35 for p in inside)))
        at_laptop.append(float(any(_inside(w, expand(laptop, 0.3, 0.3, 0.3, 0.3)) for w in wrists)))
        hands_desk.append(float(sum(_inside(w, expand(desk, 0.0, 0.25, 0.0, -0.3)) for w in wrists)))
        mouth = []
        for p in inside:
            nose = p.point(NOSE)
            if nose is None:
                continue
            for i in (L_WRIST, R_WRIST):
                w = p.point(i)
                if w is not None:
                    mouth.append(np.hypot((w[0] - nose[0]) / aspect, w[1] - nose[1]))
        hand_mouth.append(float(min(mouth, default=1.0) < config.hand_mouth))
        # Wrists of two different people close together: something is being passed over.
        gaps = [np.hypot((a[0] - b[0]) / aspect, a[1] - b[1])
                for i, p in enumerate(inside) for q in inside[i + 1:]
                for a in (p.point(L_WRIST), p.point(R_WRIST)) for b in (q.point(L_WRIST), q.point(R_WRIST))
                if a is not None and b is not None]
        hands_close.append(float(min(gaps, default=1.0) < config.hand_gap))
        near = far = 0
        for p in inside:
            shoulders = p.point(L_SHOULDER, R_SHOULDER)
            y = shoulders[1] if shoulders else p.box[1] + 0.2 * p.height
            if _overlap(p.box, station) > 0.2:
                if y < desk[1] + 0.02:
                    far += 1
                else:
                    near += 1
        near_count.append(near)
        far_count.append(far)
        at_station.append(float(any(_overlap(p.box, station) > 0.2 for p in inside)))
    times = pose.times
    count = np.asarray(count, float)
    near_count, far_count = np.asarray(near_count, float), np.asarray(far_count, float)
    # The cashier works on the side of the desk where people spend the most time.
    cashier_far = far_count.sum() >= near_count.sum()
    cashier_side = far_count if cashier_far else near_count
    values = {
        "persons": count,
        "room_occupied": np.asarray(occupied),
        "settled_persons": np.asarray(settled, float),
        "customer_present": np.clip(np.asarray(settled, float) - 1, 0, 1),
        "cashier_at_station": np.asarray(at_station),
        "person_in_doorway": np.asarray(doorway_person),
        "at_safe": np.asarray(at_safe),
        "using_computer": np.asarray(at_laptop),
        "hands_on_desk": np.clip(np.asarray(hands_desk), 0, 1),
        "hand_to_mouth": np.asarray(hand_mouth),
        "hands_close": np.asarray(hands_close),
    }
    # Local patch motion, resampled from the motion timeline onto the pose timeline.
    def motion_at(series: np.ndarray, reduce=np.max) -> np.ndarray:
        out = np.empty(len(times))
        for index, moment in enumerate(times):
            inside = np.abs(motion.times - moment) <= 0.13
            out[index] = reduce(series[inside]) if inside.any() else series[int(np.argmin(np.abs(motion.times - moment)))]
        return out

    magnitude = motion.magnitude
    values["door_motion"] = motion_at(motion.region(magnitude, door, np.mean))
    values["safe_motion"] = motion_at(motion.region(magnitude, safe, np.mean))
    values["desk_motion"] = motion_at(motion.region(motion.difference, regions["desk_hands"], np.mean))
    values["safe_change"] = motion_at(motion.region(motion.background, safe, np.mean), np.mean)
    values["door_change"] = motion_at(motion.region(motion.background, door, np.mean), np.mean)
    values["desk_change"] = motion_at(motion.region(motion.background, regions["desk"], np.mean), np.mean)
    screen = motion.region(motion.luminance, regions["screen"], np.mean)
    room = motion.luminance.reshape(len(motion.times), -1).mean(axis=1)
    values["screen_luminance"] = motion_at(screen, np.mean)
    values["screen_contrast"] = motion_at(motion.region(motion.luminance, regions["screen"], np.std), np.mean)
    values["room_luminance"] = motion_at(room, np.mean)
    values["cashier_far_side"] = np.full(len(times), float(cashier_far))
    values["door_delta"] = _unoccluded_change(motion, zone, times, people_in_room)
    values["safe_delta"] = _unoccluded_change(motion, safe, times, people_in_room)
    # The door differs from its appearance at the start: open, unless the lights changed
    # (then the comparison says nothing and the score stays at 0.5).
    lit = values["room_luminance"] >= config.lights_ratio * values["room_luminance"][:max(1, len(times) // 20)].mean()
    opened = 1 / (1 + np.exp(-(values["door_delta"] - config.door_change) / config.door_change_scale))
    values["door_open"] = np.where(lit, opened, 0.5)
    values["lit"] = lit.astype(float)
    return Signals(times, values, people_in_room)


def _unoccluded_change(motion: PatchMotion, box: Box, times: np.ndarray, people: list[list[Person]],
                       reference_sec: float = 1.0) -> np.ndarray:
    """Mean absolute luminance change of a region against its appearance at the start of the
    video, counting only patches that no person covers at that moment."""
    mask = motion.mask(box)
    rows, cols = motion.grid
    centres_y = (np.arange(rows) + 0.5) / rows
    centres_x = (np.arange(cols) + 0.5) / cols
    start = motion.times <= motion.times[0] + reference_sec
    reference = np.median(motion.luminance[start], axis=0)
    out = np.zeros(len(times))
    for index, moment in enumerate(times):
        sample = int(np.argmin(np.abs(motion.times - moment)))
        free = mask.copy()
        for person in people[index]:
            x0, y0, x1, y1 = person.box
            free &= ~(((centres_y >= y0) & (centres_y <= y1))[:, None] & ((centres_x >= x0) & (centres_x <= x1))[None, :])
        if free.sum() >= max(3, 0.25 * mask.sum()):
            out[index] = float(np.abs(motion.luminance[sample][free] - reference[free]).mean())
        else:
            out[index] = np.nan
    # Occluded samples carry the last visible value forward.
    for index in range(len(out)):
        if np.isnan(out[index]):
            out[index] = out[index - 1] if index > 0 else 0.0
    return out

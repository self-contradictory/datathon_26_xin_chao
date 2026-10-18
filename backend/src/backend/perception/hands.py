"""Pose-guided zoom on the hands: the body keypoints say where the hands are, the VLM looks closely.

An ID card or a few banknotes cover a handful of pixels even in the desk crop. Cropping tightly
around the wrists of the people at the desk lets the 2B model tell a card from banknotes.
"""
from backend.perception.features import FeatureConfig, deduplicate, in_room
from backend.perception.pose import L_WRIST, R_WRIST, Person
from backend.perception.regions import RegionProbe
from backend.perception.scene import Box, Scene

HAND_PROBES = (
    RegionProbe("id_document", "Is a person holding an identity card or a passport?"),
    RegionProbe("cash_in_hands", "Is a person holding banknotes?"),
    RegionProbe("counting_cash", "Is a person counting banknotes?"),
)
HAND_TOKENS = 192


def hand_box(people: list[Person], scene: Scene, config: FeatureConfig = FeatureConfig(),
             margin: tuple[float, float] = (0.07, 0.05), minimum: tuple[float, float] = (0.24, 0.13)) -> Box | None:
    """Box around the wrists that are over the desk, or None when no hands are there."""
    x0, y0, x1, y1 = scene.regions["desk_hands"]
    wrists = [w for p in deduplicate([p for p in people if in_room(p, scene, config)])
              for w in (p.point(L_WRIST), p.point(R_WRIST))
              if w is not None and x0 <= w[0] <= x1 and y0 <= w[1] <= y1]
    if not wrists:
        return None
    xs, ys = [w[0] for w in wrists], [w[1] for w in wrists]
    left, right = min(xs) - margin[0], max(xs) + margin[0]
    top, bottom = min(ys) - margin[1], max(ys) + margin[1]
    if right - left < minimum[0]:
        centre = (left + right) / 2
        left, right = centre - minimum[0] / 2, centre + minimum[0] / 2
    if bottom - top < minimum[1]:
        centre = (top + bottom) / 2
        top, bottom = centre - minimum[1] / 2, centre + minimum[1] / 2
    return float(max(0.0, left)), float(max(0.0, top)), float(min(1.0, right)), float(min(1.0, bottom))


def hand_evidence(series: dict) -> dict:
    """An ID card is held when the hand crop shows a card but not banknotes; the 2B model alone
    mistakes banknotes held up for an ID card. Other keys pass through unchanged."""
    if "id_document" not in series or "cash_in_hands" not in series:
        return series
    (times, card), (_, cash) = series["id_document"], series["cash_in_hands"]
    return series | {"id_document": (times, card * (1 - cash))}

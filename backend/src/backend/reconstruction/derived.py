from collections.abc import Callable, Iterable, Sequence
from itertools import pairwise
from typing import Any

CASHIER = "person_1"
EPSILON = 1e-6
BOUNDED = "bounded_by_observations"
# A safe or door counts as left open after this long open with nobody at it or passing through.
LEFT_OPEN_SEC = 3.0
type _Interval = dict[str, Any]
type _Decision = tuple[str | None, Iterable[str]]


def _covering(intervals: Sequence[_Interval], start: float, end: float) -> _Interval | None:
    return next((interval for interval in intervals
                 if interval["end_sec"] - interval["start_sec"] > EPSILON
                 and interval["start_sec"] <= start + EPSILON and interval["end_sec"] >= end - EPSILON), None)


def _at(intervals: Sequence[_Interval], moment: float) -> _Interval | None:
    touching = [interval for interval in intervals
                if interval["start_sec"] - EPSILON <= moment <= interval["end_sec"] + EPSILON]
    points = [interval for interval in touching if interval["end_sec"] - interval["start_sec"] <= EPSILON]
    known = [interval for interval in points or touching
             if interval["knowledge"] == BOUNDED and interval["value"] in ("true", "false")]
    return known[0] if len({interval["value"] for interval in known}) == 1 else None


def _decisive(interval: _Interval | None, value: str) -> bool:
    return interval is not None and interval["knowledge"] == BOUNDED and interval["value"] == value

def _combine(
    duration: float,
    sources: Sequence[Sequence[_Interval]],
    decide: Callable[[float, float, list[_Interval | None]], _Decision],
    breaks: Iterable[float] = (),
) -> list[_Interval]:
    points = {0.0, duration, *breaks}
    for intervals in sources:
        for interval in intervals:
            points.update((interval["start_sec"], interval["end_sec"]))
    result: list[_Interval] = []
    for start, end in pairwise(sorted(p for p in points if 0 <= p <= duration)):
        if end - start <= EPSILON:
            continue
        value, support = decide(start, end, [_covering(intervals, start, end) for intervals in sources])
        support = sorted(set(support)) if value is not None else []
        previous = result[-1] if result else None
        if previous and previous["value"] == value and abs(previous["end_sec"] - start) <= EPSILON:
            previous["end_sec"] = end
            previous["support_observation_ids"] = sorted({*previous["support_observation_ids"], *support})
            continue
        result.append({"start_sec": start, "end_sec": end, "value": value,
                       "knowledge": BOUNDED if value is not None else "unknown", "support_observation_ids": support})
    instants = sorted({i["start_sec"] for s in sources for i in s if i["end_sec"] - i["start_sec"] <= EPSILON})
    for moment in instants:
        value, support = decide(moment, moment, [_at(intervals, moment) for intervals in sources])
        if value is None:
            continue
        inside = next((r for r in result if r["start_sec"] + EPSILON < moment < r["end_sec"] - EPSILON), None)
        if inside is not None:
            if inside["value"] == value:
                continue
            tail = inside | {"start_sec": moment, "support_observation_ids": list(inside["support_observation_ids"])}
            inside["end_sec"] = moment
            result.insert(result.index(inside) + 1, tail)
        left = next((r for r in result if abs(r["end_sec"] - moment) <= EPSILON), None)
        right = next((r for r in result if abs(r["start_sec"] - moment) <= EPSILON), None)
        if left and right and left["value"] == value == right["value"]:
            continue
        result.insert(result.index(right) if right else len(result), {
            "start_sec": moment, "end_sec": moment, "value": value, "knowledge": BOUNDED,
            "support_observation_ids": sorted(set(support)),
        })
    return result

def _derived_track(identifier: str, entity: str, prop: str, intervals: list[_Interval]) -> dict[str, Any] | None:
    if not any(interval["value"] is not None for interval in intervals):
        return None
    return {"id": identifier, "entity_id": entity, "property": prop, "intervals": intervals}

def _derived_states(
    state_tracks: dict[str, list[_Interval]], visits: list[tuple[str, float, float]], duration: float
) -> list[dict[str, Any]]:
    derived: list[dict[str, Any] | None] = []
    if (area := state_tracks.get("customer_present")) is not None:
        def copy(start: float, end: float, states: list[_Interval | None]) -> _Decision:
            (state,) = states
            if state is None or state["knowledge"] != BOUNDED or state["value"] not in ("true", "false"):
                return None, []
            return state["value"], state["support_observation_ids"]

        derived.append(_derived_track("st_customer_service_active", CASHIER, "customer_service_active",
                                      _combine(duration, [area], copy)))
        for person, first, last in visits:
            def present(start: float, end: float, states: list[_Interval | None], first=first, last=last) -> _Decision:
                (state,) = states
                if _decisive(state, "false"):
                    return "false", state["support_observation_ids"]
                if _decisive(state, "true") and first - EPSILON <= start and end <= last + EPSILON:
                    return "true", state["support_observation_ids"]
                return None, []

            derived.append(_derived_track(f"st_{person}_at_cash_counter", person, "at_cash_counter",
                                          _combine(duration, [area], present, (first, last))))
    if (room := state_tracks.get("room_occupied")) is not None:
        station = state_tracks.get("cashier_at_station", [])

        def unattended(start: float, end: float, states: list[_Interval | None]) -> _Decision:
            occupied, at_station = states
            empty, staffed = _decisive(occupied, "false"), _decisive(at_station, "true")
            if empty and not staffed:
                return "true", occupied["support_observation_ids"]
            if staffed and not empty:
                return "false", at_station["support_observation_ids"]
            return None, []

        derived.append(_derived_track("st_room_unattended", "room_1", "unattended",
                                      _combine(duration, [room, station], unattended)))
    # The safe counts as left open only once the cashier has also left the desk: an open safe behind a
    # seated cashier is normal work, and flagging it raised CD05B on four clean videos (Х-8, Х-14, Х-19, Х-25).
    for key, attended_key, entity, away_key in (("safe_open", "at_safe", "safe_1", "cashier_at_station"),
                                                ("door_open", "person_in_doorway", "door_1", None)):
        if (opened := state_tracks.get(key)) is None or (attended := state_tracks.get(attended_key)) is None:
            continue
        sources = [opened, attended] + ([state_tracks[away_key]] if away_key in state_tracks else [])

        def left_open(start: float, end: float, states: list[_Interval | None]) -> _Decision:
            state, someone, *station = states
            staffed = bool(station) and _decisive(station[0], "true")
            if _decisive(state, "true") and _decisive(someone, "false") and not staffed:
                return "true", [*state["support_observation_ids"], *someone["support_observation_ids"]]
            if _decisive(state, "false"):
                return "false", state["support_observation_ids"]
            if _decisive(someone, "true") or (station and _decisive(station[0], "true")):
                return "false", (someone or station[0])["support_observation_ids"]
            return None, []

        intervals = _at_least(_combine(duration, sources, left_open), LEFT_OPEN_SEC)
        derived.append(_derived_track(f"st_{entity}_left_open", entity, "left_open", intervals))
    return [track for track in derived if track is not None]


def _at_least(intervals: list[_Interval], minimum: float, bridge: float = 1.0) -> list[_Interval]:
    """Keeps a true run only if it lasts `minimum` seconds; gaps shorter than `bridge` join runs."""
    spans = [interval for interval in intervals if interval["end_sec"] - interval["start_sec"] > EPSILON]
    runs: list[list[_Interval]] = []
    for interval in spans:
        if interval["value"] != "true":
            continue
        if runs and interval["start_sec"] - runs[-1][-1]["end_sec"] <= bridge and not any(
            other["value"] == "false" and runs[-1][-1]["end_sec"] - EPSILON <= other["start_sec"]
            and other["end_sec"] <= interval["start_sec"] + EPSILON for other in spans
        ):
            runs[-1].append(interval)
        else:
            runs.append([interval])
    for run in runs:
        if run[-1]["end_sec"] - run[0]["start_sec"] < minimum:
            for interval in run:
                interval.update(value=None, knowledge="unknown", support_observation_ids=[])
    return intervals

def _counted_receipts(
    events: list[dict[str, Any]], visits: list[tuple[str, float, float]], duration: float
) -> list[dict[str, Any]]:
    def start(event: dict[str, Any]) -> float:
        return event["time"]["start_sec"]

    tracks = []
    for person, _, last in visits:
        handed = [e for e in events if e["action"] == "cash_received"
                  and {"role": "customer", "entity_id": person} in e["participants"]]
        if not handed:
            continue
        receipt = min(handed, key=start)
        counts = [e for e in events if e["action"] == "cash_counted"
                  and e["time"]["end_sec"] > start(receipt) and start(e) <= last]
        if not counts:
            continue
        count = min(counts, key=start)
        since = count["time"]["end_sec"]
        if since >= last:
            continue
        support = sorted({*receipt["support_observation_ids"], *count["support_observation_ids"]})
        intervals = [
            {"start_sec": 0.0, "end_sec": since, "value": None, "knowledge": "unknown", "support_observation_ids": []},
            {"start_sec": since, "end_sec": last, "value": "true", "knowledge": BOUNDED,
             "support_observation_ids": support, "note": f"after {receipt['id']} and {count['id']}"},
        ]
        if last < duration - 1e-3:
            intervals.append({"start_sec": last, "end_sec": duration, "value": None, "knowledge": "unknown",
                              "support_observation_ids": []})
        tracks.append({"id": f"st_{person}_received_cash_counted", "entity_id": person,
                       "property": "received_cash_counted", "intervals": intervals})
    return tracks

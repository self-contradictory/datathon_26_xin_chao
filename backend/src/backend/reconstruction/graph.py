from itertools import pairwise

from backend.reconstruction.derived import _counted_receipts, _derived_states
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction
from backend.steg import SparseTemporalEvidenceGraph


ENTITIES = [{'id': 'person_1',
  'kind': 'person',
  'subtype': 'person',
  'identity_status': 'provisional',
  'role': 'cashier',
  'notes': 'Provisional cashier role within this video; no identity across videos.'},
 {'id': 'safe_1', 'kind': 'object', 'subtype': 'safe', 'identity_status': 'stable'},
 {'id': 'computer_1', 'kind': 'object', 'subtype': 'computer', 'identity_status': 'stable'},
 {'id': 'desk_1', 'kind': 'object', 'subtype': 'cashier_desk', 'identity_status': 'stable'},
 {'id': 'door_1', 'kind': 'object', 'subtype': 'entrance_door', 'identity_status': 'stable'},
 {'id': 'room_1', 'kind': 'zone', 'subtype': 'cash_room', 'identity_status': 'stable'},
 {'id': 'customer_area_1', 'kind': 'zone', 'subtype': 'customer_side_of_desk', 'identity_status': 'stable'}]

CLAIMS = {'cashier_seated': ('person_1', 'seated_at_desk', 'true', 'false'),
 'customer_present': ('customer_area_1', 'occupied', 'true', 'false'),
 'person_in_doorway': ('door_1', 'person_passing', 'true', 'false'),
 'counting_cash': ('person_1', 'cash_counted', 'true', 'false'),
 'handover': ('person_1', 'cash_handover', 'true', 'false'),
 'cash_from_customer': ('person_1', 'cash_received', 'true', 'false'),
 'cash_to_customer': ('person_1', 'cash_given_to_customer', 'true', 'false'),
 'using_computer': ('person_1', 'cashier_uses_computer', 'true', 'false'),
 'at_safe': ('safe_1', 'person_at_safe', 'true', 'false'),
 'eating': ('person_1', 'cashier_eats', 'true', 'false'),
 'phone': ('person_1', 'cashier_uses_phone', 'true', 'false'),
 'room_occupied': ('room_1', 'occupied', 'true', 'false'),
 'safe_open': ('safe_1', 'open', 'true', 'false'),
 'screen_on': ('computer_1', 'screen_on', 'true', 'false'),
 'cash_on_desk': ('desk_1', 'banknotes_visible', 'true', 'false'),
 'bag_on_desk': ('desk_1', 'bag_visible', 'true', 'false'),
 'food_on_desk': ('desk_1', 'food_visible', 'true', 'false'),
 'personal_items': ('desk_1', 'personal_item_visible', 'true', 'false'),
 'door_open': ('door_1', 'open', 'true', 'false'),
 'stamps_on_desk': ('desk_1', 'stamps_visible', 'true', 'false'),
 'key_in_safe': ('safe_1', 'key_in_lock', 'true', 'false'),
 'id_document': ('customer_area_1', 'physical_id_checked', 'true', 'false'),
 'cashier_at_station': ('person_1', 'at_station', 'true', 'false')}

TRANSITION_ACTIONS = {'cashier_seated': ('seated_observed', 'no_longer_seated'),
 'customer_present': ('customer_arrives', 'customer_leaves'),
 'room_occupied': ('person_becomes_visible', 'no_person_visible'),
 'safe_open': ('safe_opened', 'safe_closed'),
 'screen_on': ('screen_turned_on', 'screen_turned_off'),
 'cash_on_desk': ('banknotes_become_visible', 'banknotes_no_longer_visible'),
 'bag_on_desk': ('bag_become_visible', 'bag_no_longer_visible'),
 'food_on_desk': ('food_become_visible', 'food_no_longer_visible'),
 'personal_items': ('personal_items_become_visible', 'personal_items_no_longer_visible'),
 'door_open': ('door_opened', 'door_closed'),
 'stamps_on_desk': ('stamps_become_visible', 'stamps_no_longer_visible'),
 'key_in_safe': ('key_inserted', 'key_removed'),
 'cashier_at_station': ('cashier_returns_to_station', 'cashier_leaves_station')}

ACTION_EVENTS = {'person_in_doorway': ('person_passes_doorway', 'door_1'),
 'counting_cash': ('cash_counted', None),
 'handover': ('cash_handover', None),
 'cash_from_customer': ('cash_received', None),
 'cash_to_customer': ('cash_given_to_customer', None),
 'using_computer': ('cashier_uses_computer', 'computer_1'),
 'at_safe': ('person_at_safe', 'safe_1'),
 'eating': ('cashier_eats', None),
 'phone': ('cashier_uses_phone', None),
 'id_document': ('physical_id_checked', None)}

ROLES = {'safe_1': 'safe',
 'computer_1': 'computer',
 'desk_1': 'station',
 'door_1': 'door',
 'room_1': 'room',
 'customer_area_1': 'location'}

def _state_intervals(track: AttributeTrack, identifiers: list[str], duration: float) -> list[dict]:
    _, _, yes, no = CLAIMS[track.probe.key]
    observations = track.observations
    intervals = []
    first = observations[0].time
    if first > 0:
        intervals.append({"start_sec": 0.0, "end_sec": first, "value": None,
                          "knowledge": "unknown", "support_observation_ids": []})
    for index, segment in enumerate(track.segments):
        start, end = observations[segment.first].time, observations[segment.last].time
        known = segment.confidence >= 0.6
        intervals.append({
            "start_sec": start, "end_sec": end,
            "value": (yes if segment.value else no) if known else None,
            "knowledge": "bounded_by_observations" if known else "unknown",
            "support_observation_ids": identifiers[segment.first:segment.last + 1],
        })
        if index + 1 < len(track.segments):
            following = track.segments[index + 1]
            intervals.append({
                "start_sec": end, "end_sec": observations[following.first].time,
                "value": "transitioning", "knowledge": "bounded_by_observations",
                "support_observation_ids": [identifiers[segment.last], identifiers[following.first]],
            })
    last = observations[-1].time
    if last < duration:
        intervals.append({"start_sec": last, "end_sec": duration, "value": None,
                          "knowledge": "unknown", "support_observation_ids": []})
    return intervals


def build_timeline(reconstruction: Reconstruction) -> SparseTemporalEvidenceGraph:
    video = reconstruction.video
    tracks = reconstruction.tracks
    frame_ids = [f"f_{index}" for index in video.frame_indices]
    observations, events, state_tracks = [], [], []
    observation_ids = {}
    intervals_by_key = {}
    for key, track in tracks.items():
        subject, predicate, yes, no = CLAIMS[key]
        identifiers = []
        for index, observation in enumerate(track.observations):
            identifier = f"o{len(observations) + 1}"
            certainty = max(observation.probability, 1 - observation.probability)
            observations.append({
                "id": identifier, "timestamp_sec": observation.time,
                "subject_id": subject, "predicate": predicate,
                "value": yes if observation.probability >= 0.5 else no,
                "visibility": "unknown", "evidence_frame_ids": [frame_ids[index]],
                "source_stage": "coarse_vlm", "reliability": "medium" if certainty >= 0.7 else "low",
                "notes": f"Uncalibrated yes/no score={observation.probability:.3f}",
            })
            identifiers.append(identifier)
        observation_ids[key] = identifiers
        intervals_by_key[key] = _state_intervals(track, identifiers, video.duration)
        state_tracks.append({
            "id": f"st_{key}", "entity_id": subject, "property": predicate,
            "intervals": intervals_by_key[key],
        })

    entities = [dict(entity) for entity in ENTITIES]
    presence = tracks["customer_present"]
    visits = []
    for segment in presence.segments:
        if segment.value:
            customer = f"customer_{len(visits) + 1}"
            visits.append((customer, segment))
            entities.append({
                "id": customer, "kind": "person", "subtype": "person", "identity_status": "provisional",
                "role": "customer", "notes": "Role scoped to one presence episode; identity across visits is unknown.",
            })

    visit_spans = [(customer, presence.observations[segment.first].time, presence.observations[segment.last].time)
                   for customer, segment in visits]
    state_tracks.extend(_derived_states(intervals_by_key, visit_spans, video.duration))

    def customer_at(moment: float) -> str | None:
        return next((customer for customer, segment in visits if segment.start <= moment <= segment.end), None)

    for key, track in tracks.items():
        if key not in TRANSITION_ACTIONS:
            continue
        subject = CLAIMS[key][0]
        for left, right in pairwise(track.segments):
            before, after = track.observations[left.last].time, track.observations[right.first].time
            boundary = (before + after) / 2
            rise, fall = TRANSITION_ACTIONS[key]
            if subject == "person_1":
                participants = [{"role": "cashier", "entity_id": subject}, {"role": "station", "entity_id": "desk_1"}]
            elif key == "customer_present":
                customer = next(customer for customer, segment in visits if segment is (right if right.value else left))
                participants = [{"role": "customer", "entity_id": customer},
                                {"role": "cashier", "entity_id": "person_1"}, {"role": "station", "entity_id": "desk_1"}]
            else:
                participants = [{"role": ROLES[subject], "entity_id": subject}]
            events.append({
                "id": f"e{len(events) + 1}", "action": rise if right.value else fall,
                "time": {"start_sec": boundary, "end_sec": boundary,
                         "start_uncertainty_sec": boundary - before, "end_uncertainty_sec": after - boundary},
                "participants": participants,
                "support_observation_ids": [observation_ids[key][left.last], observation_ids[key][right.first]],
                "evidence_frame_ids": [frame_ids[left.last], frame_ids[right.first]],
                "inference_status": "inferred_from_observations", "verification_status": "first_pass",
            })

    for key, (action, obj) in ACTION_EVENTS.items():
        track = tracks[key]
        identifiers = observation_ids[key]
        for segment in track.segments:
            if not segment.value:
                continue
            first, last = segment.first, segment.last
            start, end = track.observations[first].time, track.observations[last].time
            previous = track.observations[first - 1].time if first > 0 else start
            following = track.observations[last + 1].time if last + 1 < len(track.observations) else end
            ranked = sorted(range(first, last + 1), key=lambda i: -abs(track.observations[i].probability - 0.5))
            participants = []
            if key in {"counting_cash", "handover", "cash_from_customer", "cash_to_customer", "using_computer", "eating", "phone"}:
                participants.append({"role": "cashier", "entity_id": "person_1"})
            if key in {"counting_cash", "handover", "cash_from_customer", "cash_to_customer", "id_document"}:
                customer = customer_at((start + end) / 2)
                if customer:
                    participants.append({"role": "customer", "entity_id": customer})
            if obj:
                participants.append({"role": ROLES[obj], "entity_id": obj})
            if not participants:
                participants.append({"role": "location", "entity_id": "room_1"})
            events.append({
                "id": f"e{len(events) + 1}", "action": action,
                "time": {"start_sec": start, "end_sec": end,
                         "start_uncertainty_sec": start - previous, "end_uncertainty_sec": following - end},
                "participants": participants,
                "support_observation_ids": identifiers[first:last + 1],
                "evidence_frame_ids": [frame_ids[index] for index in sorted(ranked[:3])],
                "inference_status": "inferred_from_observations" if segment.confidence >= 0.8 else "hypothesis",
                "verification_status": "first_pass",
            })

    state_tracks.extend(_counted_receipts(events, visit_spans, video.duration))
    episodes = []
    for customer, segment in visits:
        open_ended = segment.last == len(presence.observations) - 1
        episodes.append({
            "id": f"ep{len(episodes) + 1}", "kind": "customer_visit", "start_sec": segment.start,
            "end_sec": None if open_ended else segment.end,
            "end_boundary_status": "unknown" if open_ended else "inferred",
            "event_ids": [event["id"] for event in events
                          if event["time"]["end_sec"] >= segment.start and event["time"]["start_sec"] <= segment.end
                          and not any(participant["role"] == "customer" and participant["entity_id"] != customer
                                      for participant in event["participants"])],
            "basis_observation_ids": observation_ids["customer_present"][segment.first:segment.last + 1],
        })

    return SparseTemporalEvidenceGraph.model_validate({
        "schema_version": "1.0.0",
        "video": {"id": video.path.stem, "source_ref": video.path.name, "duration_sec": video.duration,
                  "time_unit": "seconds_from_start", "has_audio_used": False,
                  "width_px": video.width, "height_px": video.height, "nominal_fps": video.native_fps},
        "processing": {"observer_model": reconstruction.observer_model, "observer_version": "hf-local",
                       "scan_sample_fps": video.sample_fps, "window_sec": 1.0 / video.sample_fps,
                       "stride_sec": 1.0 / video.sample_fps, "runtime_local": True,
                       "pipeline_version": "questions-v1"},
        "evidence_frames": [{"id": identifier, "timestamp_sec": float(moment), "source_ref": video.path.name,
                             "original_frame_index": index}
                            for identifier, moment, index in zip(frame_ids, video.times, video.frame_indices, strict=True)],
        "entities": entities, "observations": observations,
        "events": sorted(events, key=lambda event: (event["time"]["start_sec"], event["id"])),
        "state_tracks": state_tracks, "relation_tracks": [],
        "observation_coverage": {"scan_windows": [{"id": "w_scan", "start_sec": 0.0,
                                 "end_sec": video.duration, "status": "processed", "sampled_frame_ids": frame_ids}],
                                 "entity_visibility_intervals": []},
        "procedure_episodes": episodes, "quality_flags": [],
    })

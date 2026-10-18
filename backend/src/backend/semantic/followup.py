"""Plain-text visual follow-ups; validated facts and IDs are assembled by Python."""
import re

from backend.followup.models import FrameFact, ObservedAction, VisualAnswer
from backend.followup.observer import sample_window
from backend.followup.semantic import SemanticMatcher
from backend.reconstruction.graph import CLAIMS
from backend.reconstruction.derived import _counted_receipts, _derived_states
from backend.reconstruction.probes import PERCEPTION_PROBES
from backend.rules.index import STEGIndex
from backend.rules.models import EntityByKind, StateMatcher
from backend.steg import Participant, SemanticSupport, StateTrack

EVENT_QUESTIONS = {
    "physical_id_checked": "Is the cashier visibly examining or verifying a customer's ID card or passport?",
    "cash_counted": "Is the cashier visibly counting banknotes by hand or with the counting machine?",
    "cash_received": "Is the cashier receiving banknotes from the customer?",
    "cash_given_to_customer": "Is the cashier giving banknotes to the customer?",
    "cash_handover": "Are banknotes visibly being passed between the cashier and the customer?",
    "cashier_eats": "Is the cashier visibly eating food or drinking?",
    "cashier_uses_phone": "Is the cashier using a mobile phone?",
    "cashier_uses_computer": "Is the cashier typing on the computer?",
}
UNCERTAIN_ACTION = re.compile(r"\b(appears?|seems?|suggests?|suggesting|possibly|maybe|might|could|unclear|uncertain)\b", re.IGNORECASE)


def event_participants(question, graph):
    """Resolve existing actors only; omitted matcher roles are not a request to skip vision."""
    entities = {e.id: e for e in graph.entities if e.identity_status != "ambiguous"}
    index = STEGIndex(graph)
    episode = index.episodes.get(question.episode_id)
    roles = question.matcher.participants or {}
    requested = list(roles.items()) or ([("cashier", "$cashier")] if question.matcher.action in EVENT_QUESTIONS else [])
    result = []
    for role, variable in requested:
        identifier = question.bindings.get(variable)
        if variable in question.bindings and identifier not in entities:
            return []
        if identifier not in entities and episode is not None:
            identifier, problem = index.episode_role(episode, role)
            if problem == "ambiguous_role":
                return []
        if identifier not in entities:
            candidates = [e.id for e in entities.values() if e.kind == "person" and e.role == role]
            identifier = candidates[0] if len(candidates) == 1 else None
        if identifier not in entities:
            return []
        result.append(Participant(role=role, entity_id=identifier))
    if not requested:
        # An anchor can provide participants for an action without an explicit actor vocabulary.
        anchored = [e for e in graph.events if e.id in question.window.anchor_ids and e.action == question.matcher.action]
        if len(anchored) == 1 and all(p.entity_id in entities for p in anchored[0].participants):
            result = anchored[0].participants
    return result


def refresh_derived_states(graph):
    """Recompute deterministic states so replayed evidence cannot leave stale derived claims."""
    index = STEGIndex(graph)
    visits = []
    for episode in graph.procedure_episodes:
        if episode.kind == "customer_visit":
            customer, _ = index.episode_role(episode, "customer")
            if customer:
                visits.append((customer, episode.start_sec, episode.end_sec or graph.video.duration_sec))
    sources = {}
    for key, (entity, prop, _, _) in CLAIMS.items():
        tracks = [t for t in graph.state_tracks if t.entity_id == entity and t.property == prop]
        if tracks:
            sources[key] = [i.model_dump(mode="json") for t in tracks for i in t.intervals]
    generated = _derived_states(sources, visits, graph.video.duration_sec)
    generated += _counted_receipts([e.model_dump(mode="json") for e in graph.events], visits, graph.video.duration_sec)
    derived_ids = {"st_room_unattended", "st_customer_service_active", "st_safe_1_left_open", "st_door_1_left_open"}
    derived_ids |= {t.id for t in graph.state_tracks if t.id.startswith("st_customer_")
                    and t.property in {"at_cash_counter", "received_cash_counted"}}
    derived_ids |= {t["id"] for t in generated}
    result = graph.model_copy(deep=True)
    result.state_tracks = [t for t in result.state_tracks if t.id not in derived_ids]
    result.state_tracks.extend(StateTrack.model_validate(t) for t in generated)
    result.semantic_supports = [s for s in result.semantic_supports if s.record_id not in derived_ids]
    return result


class TextSemanticMatcher(SemanticMatcher):
    def run(self, graph, candidates):
        self.seen.update(item["key"] for item in candidates)
        links = []
        for item in candidates:
            record = item["context"]
            context = f"Observed {item['kind']}: {item['observed'].replace('_', ' ')}. "
            subject = record.get("entity_id") or record.get("subject_id")
            if subject:
                entity = next((e for e in graph.entities if e.id == subject), None)
                if entity:
                    context += f" Subject is the {entity.role or entity.subtype.replace('_', ' ')}. "
            context += str(record.get("note") or record.get("notes") or "")
            for actor in record.get("participants", []):
                context += f" Participant {actor['entity_id']} has role {actor['role']}."
            for interval in record.get("intervals", []):
                context += f" From {interval['start_sec']} to {interval['end_sec']} seconds, value "
                context += f"{interval.get('value', interval.get('target_status', 'unknown'))}; knowledge {interval.get('knowledge', 'unknown')}."
            questions = [f"Does this {item['kind']} claim establish '{term.replace('_', ' ')}' "
                         "with the same actor, object, direction and specificity?" for term in item["requirements"]]
            scores = self.model.entail(context, questions)
            for term, (yes, no, unclear) in zip(item["requirements"], scores, strict=True):
                if yes < 0.85 or unclear >= yes:
                    continue
                # Property aliases need truth-preserving equivalence; entailment alone is insufficient.
                equivalent = False
                if item["kind"] in {"action", "entity", "role", "episode"}:
                    reverse = self.model.entail(f"The claim is {term.replace('_', ' ')}.",
                                               [f"Does this necessarily mean {item['observed'].replace('_', ' ')}?"])[0]
                    equivalent = reverse[0] >= 0.85
                links.append(SemanticSupport(record_id=item["record_id"], kind=item["kind"],
                             observed=item["observed"], requirement=term, supports=True,
                             equivalent=equivalent, reason="Directional entailment of the observed claim"))
        return graph.model_copy(update={"semantic_supports": graph.semantic_supports + links})


def resolve_entity(selector, question, graph):
    index = STEGIndex(graph)
    if isinstance(selector, str):
        result = question.bindings.get(selector)
    elif isinstance(selector, EntityByKind):
        matches = index.entities_of(selector.kind, selector.subtype)
        result = matches[0] if len(matches) == 1 else None
    else:
        episode = index.episodes.get(question.episode_id)
        result = index.episode_role(episode, selector.episode_role)[0] if episode else None
    return result if result in index.entities else None


class TextObserver:
    def __init__(self, model, video, max_frames=4, threshold=0.85):
        self.model, self.video, self.max_frames, self.threshold = model, video, max_frames, threshold
        self.records = []

    def supports(self, question):
        return question.matcher.kind in {"state", "event", "relation"}

    def answer(self, question, graph):
        frames = sample_window(self.video, question.window.start_sec, question.window.end_sec, self.max_frames)
        if not frames:
            raise ValueError("No frames available in follow-up window")
        matcher = question.matcher
        facts, actions, text_records = [], [], []
        abstention_reason = None
        if matcher.kind == "state":
            subject = resolve_entity(matcher.entity, question, graph)
            entity = next((e for e in graph.entities if e.id == subject), None)
            if entity is not None and matcher.property == "left_open" and subject in {"safe_1", "door_1"}:
                # Ask for visible components. "Left open" includes a duration and is not a visual atom.
                components = [("open", "true"), ("person_at_safe" if subject == "safe_1" else "person_passing", "false")]
                for prop, value in components:
                    component = question.model_copy(update={"id": question.id + "_" + prop,
                        "matcher": StateMatcher(kind="state", entity=matcher.entity, property=prop, value=value)})
                    answer, _ = self.answer(component, graph)
                    facts.extend(answer.facts)
                return VisualAnswer(status="observed" if facts else "not_visible", facts=facts,
                                    explanation="Visible components only; duration is checked by deterministic rules."), frames
            if entity is not None:
                key = next((key for key, claim in CLAIMS.items() if claim[:2] == (subject, matcher.property)), None)
                probe = next((p for p in PERCEPTION_PROBES if p.key == key), None)
                query = probe.question if probe else f"Is the {entity.subtype.replace('_', ' ')} in state {matcher.property.replace('_', ' ')}?"
                for frame in frames:
                    text = self.model.text("Write one ordinary English sentence beginning 'The image shows' that describes "
                                           "the visible evidence relevant to this question: " + query +
                                           " Say the detail is unclear when it cannot be seen. Do not infer unseen facts. "
                                           "Use a sentence, without field names, braces, lists or JSON.",
                                           [frame.image], max_new_tokens=64)
                    scores = self.model.entail(text, [query])[0]
                    text_records.append({"frame_id": frame.evidence.id, "text": text, "scores": scores})
                    yes, no, unclear = scores
                    if max(yes, no) >= self.threshold and unclear < max(yes, no):
                        facts.append(FrameFact(frame_id=frame.evidence.id, subject_id=subject,
                                     predicate=matcher.property, value="true" if yes > no else "false",
                                     visibility="clear", reliability="medium"))
            else:
                abstention_reason = "State subject cannot be grounded uniquely."
        elif matcher.kind == "event":
            participants = event_participants(question, graph)
            query = EVENT_QUESTIONS.get(matcher.action, "Is this action explicitly visible: " + matcher.action.replace("_", " ") + "?")
            # Vision always runs, including when the rule omitted participants or actors cannot be bound.
            text = self.model.text("Write one ordinary English sentence describing the visible evidence relevant to: "
                                   + query + " These frames are chronological. Preserve who acts, the object and "
                                   "direction of transfer. Holding a card alone does not prove ID verification. "
                                   "Say unclear when necessary. Use prose, without JSON, field names or invented IDs.",
                                   [frame.image for frame in frames], max_new_tokens=80)
            scores = self.model.entail(text, [query])[0]
            text_records.append({"frame_ids": [f.evidence.id for f in frames], "text": text, "scores": scores})
            if not participants:
                abstention_reason = "Visible text was collected, but the actor cannot be grounded uniquely."
            elif UNCERTAIN_ACTION.search(text):
                # A classifier preference cannot upgrade the narrator's speculation to an observed action.
                abstention_reason = "The description hedges or speculates about the action; it remains uncertain."
            elif scores[0] >= self.threshold and scores[0] > max(scores[1:]):
                actions.append(ObservedAction(action=matcher.action, first_frame_id=frames[0].evidence.id,
                               last_frame_id=frames[-1].evidence.id, participants=participants,
                               evidence_frame_ids=[f.evidence.id for f in frames],
                               reliability="high" if scores[0] >= 0.95 else "medium",
                               description="Plain-text follow-up, localized only to the sampled window: " + text))
            else:
                abstention_reason = "Description does not explicitly establish the requested action; absence is not proved."
        elif matcher.kind == "relation":
            subject = resolve_entity(matcher.subject, question, graph)
            target = resolve_entity(matcher.target, question, graph)
            entities = {e.id: e for e in graph.entities}
            if subject in entities and target in entities:
                left = entities[subject].role or entities[subject].subtype.replace("_", " ")
                right = entities[target].role or entities[target].subtype.replace("_", " ")
                query = f"Is the {left} visibly {matcher.relation.replace('_', ' ')} relative to the {right}?"
                for frame in frames:
                    text = self.model.text("Describe the visible evidence relevant to this question in one English sentence: "
                                           + query + " Preserve the direction. Say unclear if it cannot be seen. No JSON.",
                                           [frame.image], max_new_tokens=64)
                    scores = self.model.entail(text, [query])[0]
                    text_records.append({"frame_id": frame.evidence.id, "text": text, "scores": scores})
                    yes, no, unclear = scores
                    if max(yes, no) >= self.threshold and unclear < max(yes, no):
                        facts.append(FrameFact(kind="relation", frame_id=frame.evidence.id, subject_id=subject,
                                     predicate=matcher.relation, value="true" if yes > no else "false",
                                     object_entity_id=target if yes > no else None, visibility="clear", reliability="medium"))
            else:
                abstention_reason = "Relation endpoints cannot be grounded uniquely."
        # Relations and ungrounded participants abstain. A negative action answer never proves omission.
        self.records.append({"question_id": question.id, "rule_id": question.rule_id,
                             "observations": text_records, "facts": len(facts), "actions": len(actions),
                             "abstention_reason": abstention_reason if not facts and not actions else None})
        return VisualAnswer(status="observed" if facts or actions else "not_visible", facts=facts, actions=actions,
                            explanation="Plain-text evidence normalized by the application; unmentioned details remain unknown."), frames

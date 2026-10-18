import hashlib
import json

from backend.followup.models import EvidenceQuestion, TimeWindow
from backend.rules.findings import EvaluationReport, Finding
from backend.rules.index import STEGIndex, at_instant, throughout
from backend.rules.matching import RuleMatcher
from backend.rules.models import EventMatcher, Rule
from backend.steg import SparseTemporalEvidenceGraph


def _window(index, finding, rule, matcher, relation="at", start=None, end=None, anchors=None):
    episode = index.episodes.get(finding.episode_id or finding.trigger_id)
    event = index.events.get(finding.trigger_id)
    scope_end = index.episode_bounds(episode).latest_end if episode else index.duration
    bounds = index.bounds(event) if event else None
    if start is None:
        start = bounds.earliest_start if bounds else finding.start_sec
    if end is None:
        end = bounds.latest_start if bounds else finding.end_sec
    bindings = dict(finding.bindings)
    if episode is not None:
        for role, variable in (getattr(rule.scope, "episode_roles", None) or {}).items():
            entity, _ = index.episode_role(episode, role)
            if entity is not None:
                bindings.setdefault(variable, entity)
    if event:
        for role, variable in (getattr(matcher, "participants", None) or {}).items():
            holders = {p.entity_id for p in event.participants if index.supports("role", event.id, p.role, role)}
            if len(holders) == 1:
                bindings.setdefault(variable, next(iter(holders)))
    start, end = max(0.0, start), min(scope_end, end)
    if end < start:
        return None
    payload = {"matcher": matcher.model_dump(mode="json"), "start": start, "end": end,
               "bindings": bindings, "episode": finding.episode_id}
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return EvidenceQuestion(
        id=f"q_{key}", rule_id=rule.rule_id, matcher=matcher,
        window=TimeWindow(relation=relation, start_sec=start, end_sec=end,
                          anchor_ids=anchors or [finding.trigger_id]),
        bindings=bindings, episode_id=episode.id if episode else None, reason=finding.reason,
    )


def _targets(rule: Rule, finding: Finding, index: STEGIndex):
    logic = rule.logic
    event = index.events.get(finding.trigger_id)
    episode = index.episodes.get(finding.episode_id or finding.trigger_id)
    scope_end = index.episode_bounds(episode).latest_end if episode else index.duration
    bounds = index.bounds(event) if event else None
    start = bounds.earliest_end if bounds else finding.start_sec
    run = RuleMatcher(rule, index)
    pool = index.members(episode) if episode else list(index.events.values())
    if rule.type in {"FORBIDDEN", "CONDITIONAL", "ROLE_RELATION"}:
        for matcher in getattr(logic, "when_all", getattr(logic, "if_all", getattr(logic, "all_of", []))):
            yield matcher, "at", None, None, None
    elif rule.type == "DURING":
        yield logic.required, "during", bounds.earliest_start if bounds else finding.start_sec, bounds.latest_end if bounds else finding.end_sec, None
    elif rule.type == "STATE_INVARIANT":
        boundaries = run.occurrences(logic.until, pool, finding.bindings, {})
        ends = [index.bounds(item).latest_start for item, _ in boundaries if item.time.start_sec >= start]
        yield logic.required, "until", start, min(ends, default=scope_end), [finding.trigger_id] + [item.id for item, _ in boundaries]
    elif rule.type == "MUTUAL_EXCLUSION":
        yield logic.other, "during", finding.start_sec, finding.end_sec, None
    elif rule.type == "REQUIRED_ACTION":
        yield logic.must, "after", start, scope_end, None
    elif rule.type == "TIMEOUT":
        yield logic.must, "after", start, min(scope_end, (bounds.latest_end if bounds else start) + logic.within_seconds), None
    elif rule.type == "PRECEDENCE":
        boundaries = [item for item, _ in run.occurrences(logic.before, pool, finding.bindings, {}) if item.time.start_sec >= start]
        boundary = min(boundaries, key=lambda item: item.time.start_sec) if boundaries else None
        yield logic.must_precede, "between" if boundary else "after", start, index.bounds(boundary).latest_start if boundary else scope_end, [finding.trigger_id] + ([boundary.id] if boundary else [])
    elif rule.type == "PROCEDURE":
        steps = {step.id: step for step in logic.steps}
        observed = {step.id: [event for matcher in step.any_of
                              for event, _ in run.occurrences(matcher, pool, finding.bindings, {})]
                    for step in logic.steps}
        for step in logic.steps:
            if observed[step.id] and finding.unknown_kind != "uncertain_order":
                for matcher in step.while_ or []:
                    for item in observed[step.id]:
                        yield matcher, "during", item.time.start_sec, item.time.end_sec, [item.id]
                continue
            previous = [event for edge in logic.order_constraints if edge.after == step.id for event in observed[edge.before]]
            following = [event for edge in logic.order_constraints if edge.before == step.id for event in observed[edge.after]]
            lower = max((index.bounds(item).earliest_end for item in previous), default=episode.start_sec if episode else 0.0)
            upper = min((index.bounds(item).latest_start for item in following), default=scope_end)
            relation = "between" if previous and following else "after" if previous else "before" if following else "range"
            for matcher in steps[step.id].any_of:
                yield matcher, relation, lower, upper, [item.id for item in previous + following]
    elif rule.type == "CARDINALITY":
        matcher = EventMatcher(kind="event", action=logic.cashier_from.event_action,
                               participants={logic.cashier_from.participant_role: "$cashier"})
        yield matcher, "during", episode.start_sec if episode else 0.0, scope_end, None
    elif rule.type == "SEPARATION":
        matcher = EventMatcher(kind="event", action=logic.origin.event_action,
                               participants={logic.origin.bundle_participant_role: "$bundle"})
        yield matcher, "before", 0.0, finding.start_sec, None
    else:
        yield rule.trigger, "range", episode.start_sec if episode else 0.0, scope_end, None
    if finding.unknown_kind in {"missing_binding", "ambiguous_role", "weak_evidence"}:
        yield rule.trigger, "during", finding.start_sec, finding.end_sec, None


def plan_questions(rules: list[Rule], graph: SparseTemporalEvidenceGraph, report: EvaluationReport,
                   include_violations: bool = False) -> list[EvidenceQuestion]:
    index = STEGIndex(graph)
    by_id = {rule.rule_id: rule for rule in rules}
    questions = {}
    for finding in report.findings(*(("UNKNOWN", "VIOLATION") if include_violations else ("UNKNOWN",))):
        rule = by_id[finding.rule_id]
        targets = list(_targets(rule, finding, index))
        if finding.outcome == "VIOLATION":
            targets.append((rule.trigger, "during", finding.start_sec, finding.end_sec, None))
        for matcher, relation, start, end, anchors in targets:
            question = _window(index, finding, rule, matcher, relation, start, end, anchors)
            if question is not None:
                if matcher.kind in {"state", "relation"}:
                    episode = index.episodes.get(question.episode_id)
                    pool = index.members(episode) if episode else list(index.events.values())
                    check = RuleMatcher(rule, index).condition(
                        matcher, question.bindings, {}, episode,
                        (question.window.start_sec, question.window.end_sec),
                        at_instant if relation == "at" else throughout, pool,
                    )
                    if check.truth != "UNKNOWN" and finding.outcome != "VIOLATION":
                        continue
                questions.setdefault(question.id, question)
    for evaluation in report.rules:
        if evaluation.findings:
            continue
        rule = by_id[evaluation.rule_id]
        matcher = rule.trigger
        if not isinstance(matcher, EventMatcher):
            continue
        decisions = {(link.kind, link.record_id, link.observed, link.requirement): link
                     for link in graph.semantic_supports}
        for link in decisions.values():
            if link.kind != "action" or link.supports is not None or link.requirement != matcher.action:
                continue
            event = index.events.get(link.record_id)
            if event is None:
                continue
            episodes = ([episode for episode in index.episodes_of(rule.scope.episode_kind)
                         if event.id in episode.event_ids] if rule.scope.kind == "episode" else [None])
            for episode in episodes:
                bindings = {}
                for role, variable in (matcher.participants or {}).items():
                    holders = {p.entity_id for p in event.participants if index.supports("role", event.id, p.role, role)}
                    if len(holders) == 1:
                        bindings[variable] = next(iter(holders))
                if episode is not None:
                    bindings[rule.scope.bind] = episode.id
                    for role, variable in (rule.scope.episode_roles or {}).items():
                        entity, _ = index.episode_role(episode, role)
                        if entity is not None:
                            bindings.setdefault(variable, entity)
                payload = {"rule": rule.rule_id, "record": link.record_id,
                           "episode": episode.id if episode else None}
                key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
                bounds = index.bounds(event)
                questions[f"q_{key}"] = EvidenceQuestion(
                    id=f"q_{key}", rule_id=rule.rule_id, matcher=matcher,
                    window=TimeWindow(relation="during", start_sec=bounds.earliest_start,
                                      end_sec=bounds.latest_end, anchor_ids=[event.id]),
                    bindings=bindings, episode_id=episode.id if episode else None, reason=link.reason,
                )
    return list(questions.values())

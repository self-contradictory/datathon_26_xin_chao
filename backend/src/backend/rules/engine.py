from collections.abc import Callable, Iterable
from dataclasses import replace

from backend.rules.evaluation import (
    TRIGGER_ENTITY,
    Context,
    Decision,
    Trigger,
    Undetermined,
    unknown,
)
from backend.rules.findings import EvaluationReport, Finding, FrameRef, Mode, RuleEvaluation
from backend.rules.index import Evidence, STEGIndex
from backend.rules.matching import RuleMatcher
from backend.rules.models import Rule, RuleRegistry, RuleType
from backend.rules.ordering_rules import precedence, required_action, timeout
from backend.rules.procedure_rules import cardinality, procedure, separation
from backend.rules.state_rules import (
    conditional,
    during,
    forbidden,
    mutual_exclusion,
    role_relation,
    state_invariant,
)
from backend.rules.triggers import contexts, triggers
from backend.steg import SparseTemporalEvidenceGraph


EVALUATORS: dict[RuleType, Callable[[RuleMatcher, Context, Trigger], Decision]] = {
    "FORBIDDEN": forbidden,
    "REQUIRED_ACTION": required_action,
    "PRECEDENCE": precedence,
    "DURING": during,
    "STATE_INVARIANT": state_invariant,
    "CONDITIONAL": conditional,
    "TIMEOUT": timeout,
    "CARDINALITY": cardinality,
    "MUTUAL_EXCLUSION": mutual_exclusion,
    "ROLE_RELATION": role_relation,
    "SEPARATION": separation,
    "PROCEDURE": procedure,
}


def evaluate_rule(rule: Rule, index: STEGIndex) -> RuleEvaluation:
    run = RuleMatcher(rule, index)
    evaluator = EVALUATORS[rule.logic.type]
    findings = []
    for context in contexts(run):
        matches = triggers(run, context)
        if rule.type == "PROCEDURE":
            matches = matches[:1]
        for trigger in matches:
            try:
                decision = evaluator(run, context, trigger)
            except Undetermined as error:
                decision = unknown(error.kind, error.reason)
            if decision.outcome == "VIOLATION" and trigger.weak:
                decision = replace(
                    decision, outcome="UNKNOWN", kind="weak_evidence",
                    reason=f"{decision.reason}, but {trigger.weak}",
                )
            findings.append(_finding(run, context, trigger, decision))
    return RuleEvaluation(
        rule_id=rule.rule_id, version=rule.version, status=rule.status,
        type=rule.type, findings=findings,
    )


def _finding(run: RuleMatcher, context: Context, trigger: Trigger, verdict: Decision) -> Finding:
    evidence = Evidence()
    evidence.merge(trigger.evidence)
    evidence.merge(verdict.evidence)
    if context.episode is not None:
        evidence.episodes.add(context.episode.id)
    references = (
        evidence.events | evidence.state_tracks | evidence.relation_tracks
        | evidence.episodes | set(trigger.values.values())
    )
    flags = run.index.flags_for(references)
    outcome, kind, reason = verdict.outcome, verdict.kind, verdict.reason
    critical = [flag for flag in flags if flag.severity == "critical"]
    if outcome == "VIOLATION" and critical:
        outcome, kind = "UNKNOWN", "critical_quality_flag"
        reason = f"{reason}; critical quality flag {critical[0].id}: {critical[0].note}"
    time = verdict.time if verdict.time is not None else trigger.bounds.start
    start, end = verdict.span or (trigger.bounds.start, trigger.bounds.end)
    rule = run.rule
    return Finding(
        rule_id=rule.rule_id, rule_version=rule.version, rule_type=rule.type, rule_status=rule.status,
        name=rule.name, category=rule.category, production=rule.status == "active",
        outcome=outcome, unknown_kind=kind if outcome == "UNKNOWN" else None, reason=reason,
        details=verdict.details, timecode_sec=time, start_sec=min(start, end), end_sec=max(start, end),
        trigger_id=trigger.ref, episode_id=context.episode.id if context.episode else None,
        bindings={k: v for k, v in sorted((trigger.values | verdict.bindings).items()) if k != TRIGGER_ENTITY},
        event_ids=sorted(evidence.events), state_track_ids=sorted(evidence.state_tracks),
        relation_track_ids=sorted(evidence.relation_tracks), episode_ids=sorted(evidence.episodes),
        observation_ids=sorted(evidence.observations), quality_flag_ids=[flag.id for flag in flags],
        evidence_frames=_frames(run, evidence, time), source=rule.source,
    )


def _frames(run: RuleMatcher, evidence: Evidence, time: float) -> list[FrameRef]:
    limit = run.policy.max_evidence_frames
    candidates = run.index.frames_for(evidence) or run.index.nearest_frames(time, limit)
    chosen = sorted(candidates.items(), key=lambda item: (abs(item[1] - time), item[1], item[0]))[:limit]
    return [FrameRef(id=frame, timestamp_sec=moment) for frame, moment in sorted(chosen, key=lambda i: (i[1], i[0]))]


def select_rules(rules: Iterable[Rule], mode: Mode) -> list[Rule]:
    allowed = {"active"} if mode == "production" else {"active", "candidate"}
    return [rule for rule in rules if rule.status in allowed]


def evaluate(
    rules: Iterable[Rule] | RuleRegistry,
    graph: SparseTemporalEvidenceGraph | STEGIndex,
    mode: Mode = "production",
) -> EvaluationReport:
    registry_id = rules.registry_id if isinstance(rules, RuleRegistry) else None
    rules = rules.rules if isinstance(rules, RuleRegistry) else rules
    index = graph if isinstance(graph, STEGIndex) else STEGIndex(graph)
    return EvaluationReport(
        video_id=index.graph.video.id,
        registry_id=registry_id,
        mode=mode,
        rules=[evaluate_rule(rule, index) for rule in select_rules(rules, mode)],
    )

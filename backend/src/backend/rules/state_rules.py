from backend.rules.evaluation import (
    Check,
    Context,
    Decision,
    Failures,
    Quantifier,
    Trigger,
    Undetermined,
    first_unknown,
    format_time,
    unknown,
)
from backend.rules.findings import Outcome
from backend.rules.index import (
    Bounds,
    EPSILON,
    Evidence,
    at_instant,
    conjunction,
    matching_runs,
    sometime,
    state_profile,
    throughout,
)
from backend.rules.matching import RuleMatcher
from backend.rules.models import Matcher, StateMatcher
from backend.steg import ProcedureEpisode


def _conjunctive(
    run: RuleMatcher,
    matchers: list[Matcher],
    context: Context,
    trigger: Trigger,
    window: tuple[float, float],
    quantifier: Quantifier,
    otherwise: Outcome,
) -> Decision:
    values, failures = dict(trigger.values), dict(trigger.failures)
    checks = []
    for matcher in matchers:
        check = run.condition(matcher, values, failures, context.episode, window, quantifier, context.pool)
        values.update(check.values)
        checks.append(check)
    evidence = Evidence()
    for check in checks:
        evidence.merge(check.evidence)
    details = [check.reason for check in checks]
    truth = conjunction(check.truth for check in checks)
    if truth == "TRUE":
        reason = "every condition held" if checks else "the trigger itself is prohibited"
        return Decision("VIOLATION", f"{reason}: " + "; ".join(details) if details else reason,
                        time=trigger.bounds.start, evidence=evidence, details=details, bindings=values)
    if truth == "FALSE":
        failed = next(check for check in checks if check.truth == "FALSE")
        return Decision(otherwise, f"condition not met: {failed.reason}", evidence=evidence,
                        details=details, bindings=values)
    kind, reason = first_unknown(checks)
    return unknown(kind, reason, evidence=evidence, details=details, bindings=values)


def forbidden(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    return _conjunctive(run, logic.when_all, context, trigger, trigger.bounds.start_window, at_instant, "CLEAR")


def role_relation(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    return _conjunctive(run, logic.all_of, context, trigger, trigger.bounds.start_window, at_instant, "CLEAR")


def conditional(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    window = trigger.bounds.certain or trigger.bounds.start_window
    return _conjunctive(run, logic.if_all, context, trigger, window, sometime, "NOT_APPLICABLE")


def holds_during(
    run: RuleMatcher,
    matcher: StateMatcher,
    bounds: Bounds,
    values: dict[str, str],
    failures: Failures,
    episode: ProcedureEpisode | None,
    label: str,
) -> Decision:
    entity = run.single(matcher.entity, values, failures, episode)
    claim = f"{entity}.{matcher.property} = {matcher.value}"
    track, pieces = run.state_pieces(entity, matcher, *bounds.possible)
    certain = bounds.certain
    if certain is not None:
        inside = [p for p in state_profile(track, *certain, matcher.value, matcher.knowledge)
                  if p.status == "contradict"]
    else:
        inside = [p for p in pieces if p.status == "contradict"] if at_instant(pieces) == "FALSE" else []
    evidence = Evidence()
    if inside:
        evidence.add_pieces(track, inside)
        first = inside[0]
        return Decision(
            "VIOLATION",
            f"{claim} was contradicted from {format_time(first.start)} while {label}",
            time=first.start, span=(first.start, inside[-1].end), evidence=evidence,
        )
    if throughout(pieces) == "TRUE":
        evidence.add_pieces(track, pieces)
        return Decision("CLEAR", f"{claim} held throughout {label}", evidence=evidence)
    margin = any(p.status == "contradict" for p in pieces)
    evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
    reason = (
        f"{claim} was contradicted only where the timing of {label} is uncertain"
        if margin else f"{claim} is not established throughout {label}"
    )
    return unknown("uncertain_order" if margin else "uncertain_state", reason, evidence=evidence)


def during(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    action = trigger.event.action if trigger.event else "the trigger"
    label = f"{action} ({trigger.ref})"
    return holds_during(run, logic.required, trigger.bounds, trigger.values, trigger.failures, context.episode, label)


def state_invariant(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    sure, doubtful = run.following(logic.until, trigger, context.pool)
    end_sure = end_maybe = context.window[1]
    boundary = f"the end of the {'episode' if context.episode else 'video'}"
    if sure:
        until = run.index.bounds(sure[0])
        end_sure, end_maybe = until.earliest_start, until.latest_start
        boundary = f"{sure[0].action} ({sure[0].id})"
    if doubtful:
        end_sure = min(end_sure, min(run.index.bounds(e).earliest_start for e in doubtful))
    start_sure, start_maybe = trigger.bounds.latest_end, trigger.bounds.earliest_end
    entity = run.single(logic.required.entity, trigger.values, trigger.failures, context.episode)
    claim = f"{entity}.{logic.required.property} = {logic.required.value}"
    evidence = Evidence()
    if end_sure > start_sure + EPSILON:
        track, pieces = run.state_pieces(entity, logic.required, start_sure, end_sure)
        breaches = [p for p in pieces if p.status == "contradict"]
        if breaches:
            evidence.add_pieces(track, breaches)
            return Decision(
                "VIOLATION",
                f"{claim} was broken at {format_time(breaches[0].start)}, before {boundary}",
                time=breaches[0].start, span=(breaches[0].start, breaches[-1].end), evidence=evidence,
            )
    track, pieces = run.state_pieces(entity, logic.required, start_maybe, max(start_maybe, end_maybe))
    evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
    if throughout(pieces) == "TRUE":
        return Decision("CLEAR", f"{claim} held until {boundary}", evidence=evidence)
    return unknown("uncertain_state", f"{claim} is not established until {boundary}", evidence=evidence)


def mutual_exclusion(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    other = logic.other
    certain = trigger.bounds.certain
    span = certain or trigger.bounds.possible
    checks: list[Check] = []
    for entity in run.resolve(other.entity, trigger.values, trigger.failures, context.episode):
        claim = f"{entity}.{other.property} = {other.value}"
        try:
            track, pieces = run.state_pieces(entity, other, *span)
        except Undetermined as error:
            checks.append(Check("UNKNOWN", error.reason, error.kind))
            continue
        overlap = matching_runs(pieces)
        evidence = Evidence()
        if overlap and certain is not None:
            overlap_span = overlap[0]
            evidence.add_pieces(track, overlap_span)
            return Decision(
                "VIOLATION", f"{claim} overlapped the trigger from {format_time(overlap_span[0].start)} to {format_time(overlap_span[-1].end)}",
                time=overlap_span[0].start, span=(overlap_span[0].start, overlap_span[-1].end), evidence=evidence,
            )
        evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
        if overlap:
            checks.append(Check("UNKNOWN", f"{claim} may overlap the trigger", "uncertain_order", evidence))
        elif sometime(pieces) == "FALSE":
            checks.append(Check("FALSE", f"{claim} did not hold during the trigger", None, evidence))
        else:
            checks.append(Check("UNKNOWN", f"{claim} is not established during the trigger", "uncertain_state", evidence))
    evidence = Evidence()
    for check in checks:
        evidence.merge(check.evidence)
    if checks and all(check.truth == "FALSE" for check in checks):
        return Decision("CLEAR", "; ".join(check.reason for check in checks), evidence=evidence)
    kind, reason = first_unknown(checks)
    return unknown(kind, reason, evidence=evidence)

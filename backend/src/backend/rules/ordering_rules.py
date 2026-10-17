from backend.rules.evaluation import Context, Decision, Trigger, Undetermined, format_time, unknown
from backend.rules.index import EPSILON, Evidence, precedes
from backend.rules.matching import RuleMatcher
from backend.steg import ProcedureEpisode


def required_action(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    episode = context.episode or _episode_of(run, trigger)
    if episode is None:
        raise Undetermined("missing_binding", "no procedure episode contains the trigger")
    members = run.index.members(episode)
    sure, doubtful = run.following(logic.must, trigger, members)
    evidence = Evidence(episodes={episode.id})
    if sure:
        evidence.add_event(sure[0])
        return Decision("CLEAR", f"{logic.must.action} ({sure[0].id}) followed the trigger",
                        time=sure[0].time.start_sec, evidence=evidence)
    if doubtful:
        event = doubtful[0]
        evidence.add_event(event)
        weak = run.weakness(event)
        return unknown("weak_evidence" if weak else "uncertain_order",
                        weak or f"the order of {event.id} and the trigger is uncertain", evidence=evidence)
    deadline = run.index.episode_bounds(episode)
    outside, _ = run.following(logic.must, trigger, [e for e in run.index.events.values() if e.id not in episode.event_ids])
    outside = [e for e in outside if e.time.start_sec <= deadline.latest_end]
    if outside:
        evidence.add_event(outside[0])
        return unknown("uncertain_order", f"{outside[0].id} matches but is not part of episode {episode.id}",
                        evidence=evidence)
    if episode.end_boundary_status == "unknown":
        return unknown("incomplete_episode", f"episode {episode.id} has no established end", evidence=evidence)
    window = (trigger.bounds.earliest_start, deadline.latest_end)
    absent, proof = run.index.proven_absent(logic.must.action, run.subjects(logic.must, trigger.values), *window)
    evidence.merge(proof)
    end = deadline.end
    missing = f"{logic.must.action} not observed between the trigger and the episode end at {format_time(end)}"
    if absent and episode.end_boundary_status == logic.deadline.requires_end_boundary:
        return Decision("VIOLATION", f"{missing}; an activity track shows it did not happen",
                        time=end, span=(trigger.bounds.start, end), evidence=evidence)
    detail = "the episode end is only inferred" if absent else "its absence is not proven"
    return unknown("not_observed", f"{missing}; {detail}", time=end, evidence=evidence)


def _episode_of(run: RuleMatcher, trigger: Trigger) -> ProcedureEpisode | None:
    if trigger.episode is not None:
        return trigger.episode
    owners = sorted(run.index.event_episodes.get(trigger.ref, set()))
    return run.index.episodes[owners[0]] if len(owners) == 1 else None


def precedence(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    boundaries, doubtful_boundaries = run.following(logic.before, trigger, context.pool)
    required, doubtful_required = run.following(logic.must_precede, trigger, context.pool)
    evidence = Evidence()
    if not boundaries:
        if required:
            evidence.add_event(required[0])
            return Decision("CLEAR", f"{logic.must_precede.action} ({required[0].id}) followed the trigger",
                            time=required[0].time.start_sec, evidence=evidence)
        if doubtful_boundaries:
            evidence.add_event(doubtful_boundaries[0])
            return unknown("uncertain_order", f"{doubtful_boundaries[0].id} may close the window", evidence=evidence)
        return Decision("NOT_APPLICABLE", f"no {logic.before.action} observed after the trigger")
    boundary = boundaries[0]
    closing = run.index.bounds(boundary)
    evidence.add_event(boundary)
    for event in required:
        if precedes(run.index.bounds(event), closing) == "TRUE":
            evidence.add_event(event)
            return Decision("CLEAR", f"{logic.must_precede.action} ({event.id}) came before {boundary.id}",
                            time=event.time.start_sec, evidence=evidence)
    pending = [e for e in required + doubtful_required if precedes(run.index.bounds(e), closing) != "FALSE"]
    if pending:
        evidence.add_event(pending[0])
        weak = run.weakness(pending[0])
        return unknown("weak_evidence" if weak else "uncertain_order",
                        weak or f"the order of {pending[0].id} and {boundary.id} is uncertain", evidence=evidence)
    window = (trigger.bounds.earliest_start, closing.latest_end)
    absent, proof = run.index.proven_absent(
        logic.must_precede.action, run.subjects(logic.must_precede, trigger.values), *window
    )
    evidence.merge(proof)
    missing = f"{logic.must_precede.action} not observed before {logic.before.action} ({boundary.id}) at {format_time(boundary.time.start_sec)}"
    if absent:
        return Decision("VIOLATION", f"{missing}; an activity track shows it did not happen",
                        time=boundary.time.start_sec, span=(trigger.bounds.start, boundary.time.start_sec),
                        evidence=evidence)
    return unknown("not_observed", f"{missing}; its absence is not proven",
                    time=boundary.time.start_sec, evidence=evidence)


def timeout(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    limit = logic.within_seconds
    earliest, latest = trigger.bounds.end_window
    evidence = Evidence()
    doubtful = []
    for event, _ in run.occurrences(logic.must, context.pool, trigger.values, trigger.failures, trigger.ref):
        bounds = run.index.bounds(event)
        if precedes(bounds, trigger.bounds) == "TRUE":
            continue
        if not run.weakness(event) and bounds.latest_start <= earliest + limit + EPSILON:
            evidence.add_event(event)
            return Decision("CLEAR", f"{event.action} ({event.id}) came within {limit:g}s",
                            time=event.time.start_sec, evidence=evidence)
        if bounds.earliest_start <= latest + limit + EPSILON:
            doubtful.append(event)
    deadline = min(trigger.bounds.end + limit, run.index.duration)
    if doubtful:
        evidence.add_event(doubtful[0])
        weak = run.weakness(doubtful[0])
        return unknown("weak_evidence" if weak else "uncertain_order",
                        weak or f"{doubtful[0].id} may fall inside the {limit:g}s limit", evidence=evidence)
    if latest + limit > run.index.duration + EPSILON:
        return unknown("incomplete_episode", f"the {limit:g}s deadline falls after the video ends")
    absent, proof = run.index.proven_absent(
        logic.must.action, run.subjects(logic.must, trigger.values), earliest, latest + limit
    )
    evidence.merge(proof)
    missing = f"{logic.must.action} not observed within {limit:g}s of the trigger ending"
    if absent:
        return Decision("VIOLATION", f"{missing}; an activity track shows it did not happen",
                        time=deadline, span=(trigger.bounds.end, deadline), evidence=evidence)
    return unknown("not_observed", f"{missing}; its absence is not proven", time=deadline, evidence=evidence)

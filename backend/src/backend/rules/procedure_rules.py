from backend.rules.evaluation import Context, Decision, Trigger, Undetermined, format_time, unknown
from backend.rules.findings import UnknownKind
from backend.rules.index import EPSILON, Evidence, precedes
from backend.rules.matching import RuleMatcher
from backend.rules.state_rules import holds_during
from backend.steg import Event, ProcedureEpisode


def cardinality(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    source = logic.cashier_from

    def cashier(episode: ProcedureEpisode) -> tuple[str | None, UnknownKind]:
        holders = {
            p.entity_id
            for event in run.index.members(episode)
            if run.index.action_matches(event, source.event_action) and not run.weakness(event)
            for p in event.participants if run.index.supports("role", event.id, p.role, source.participant_role)
        }
        if len(holders) == 1:
            return next(iter(holders)), "missing_binding"
        return None, "missing_binding" if not holders else "ambiguous_role"

    own, problem = cashier(trigger.episode)
    if own is None:
        raise Undetermined(problem, f"episode {trigger.episode.id} has no single {source.participant_role}")
    bounds = trigger.bounds
    window = (bounds.start, bounds.latest_end)
    counted = set(trigger.episode.event_ids)
    sure = [(bounds.start, bounds.earliest_end, trigger.episode.id)]
    maybe = [(bounds.start, bounds.latest_end, trigger.episode.id)]
    evidence = Evidence(episodes={trigger.episode.id})
    for other in run.index.episodes_of(logic.count.episode_kind):
        if other.id == trigger.episode.id or counted & set(other.event_ids):
            continue
        other_bounds = run.index.episode_bounds(other)
        if other_bounds.latest_end <= window[0] or other.start_sec >= window[1]:
            continue
        holder, _ = cashier(other)
        if holder is not None and holder != own:
            continue
        counted |= set(other.event_ids)
        maybe.append((other.start_sec, other_bounds.latest_end, other.id))
        if holder == own:
            sure.append((other.start_sec, other_bounds.earliest_end, other.id))
            evidence.episodes.add(other.id)
    peak, moment, active = _concurrency(sure, window)
    limit = logic.max_concurrent
    if peak > limit:
        return Decision(
            "VIOLATION", f"{own} had {peak} {logic.count.episode_kind} episodes open at {format_time(moment)} "
            f"({', '.join(active)}); the limit is {limit}", time=moment, evidence=evidence,
        )
    possible, moment, active = _concurrency(maybe, window)
    if possible > limit:
        return unknown("uncertain_order", f"up to {possible} episodes may overlap at {format_time(moment)} "
                        f"({', '.join(active)}); cashier or end not established", evidence=evidence)
    return Decision("CLEAR", f"at most {peak} {logic.count.episode_kind} episode open at once", evidence=evidence)


def separation(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    matcher = run.rule.trigger
    origin = logic.origin
    evidence = Evidence()
    origins: dict[str, str] = {}
    for role, variable in (matcher.participants or {}).items():
        if variable not in trigger.values:
            kind, reason = trigger.failures.get(variable, ("missing_binding", f"{variable} is not bound"))
            raise Undetermined(kind, reason)
        item = trigger.values[variable]
        if run.index.entities[item].identity_status == "ambiguous":
            raise Undetermined("ambiguous_role", f"{role} {item} has an ambiguous identity")
        sure, doubtful = set(), set()
        for episode in run.index.episodes.values():
            for event in run.index.members(episode):
                if run.index.action_matches(event, origin.event_action) and any(
                    run.index.supports("role", event.id, p.role, origin.bundle_participant_role)
                    and p.entity_id == item for p in event.participants
                ):
                    (doubtful if run.weakness(event) else sure).add(episode.id)
                    evidence.add_event(event)
        if not sure:
            kind = "weak_evidence" if doubtful else "missing_binding"
            raise Undetermined(kind, f"the origin episode of {item} is not established")
        if len(sure) > 1 or doubtful - sure:
            raise Undetermined("ambiguous_role", f"{item} traces to {len(sure | doubtful)} episodes")
        origins[item] = next(iter(sure))
    evidence.episodes.update(origins.values())
    trail = ", ".join(f"{item} from {episode}" for item, episode in origins.items())
    if len(set(origins.values())) > 1:
        return Decision("VIOLATION", f"items from different procedures were merged: {trail}",
                        time=trigger.bounds.start, evidence=evidence)
    return Decision("CLEAR", f"all merged items come from one procedure: {trail}", evidence=evidence)


def procedure(run: RuleMatcher, context: Context, trigger: Trigger) -> Decision:
    logic = run.rule.logic
    episode = context.episode
    members = run.index.members(episode)
    bounds = run.index.episode_bounds(episode)
    values, failures = context.values, context.failures
    evidence = Evidence(episodes={episode.id})
    results: list[Decision] = []
    observed: dict[str, tuple[list[tuple[Event, dict[str, str]]], int]] = {}
    steps = {step.id: step for step in logic.steps}

    def absent(step, end: float) -> bool:
        verified = step.omission_observability is not None
        for alternative in step.any_of:
            proven, proof = run.index.proven_absent(
                alternative.action, run.subjects(alternative, values), episode.start_sec, end, verified=verified
            )
            if not proven:
                return False
            evidence.merge(proof)
        return True

    def alternatives(step) -> str:
        return " or ".join(alternative.action for alternative in step.any_of)

    for step in logic.steps:
        found = [o for alternative in step.any_of for o in run.occurrences(alternative, members, values, failures)]
        admissible = [(event, bound) for event, bound in found if not run.weakness(event)]
        observed[step.id] = (sorted(admissible, key=lambda o: run.index.bounds(o[0]).earliest_start), len(found))
        if admissible:
            for event, _ in admissible:
                evidence.add_event(event)
            problems = []
            for condition in step.while_ or []:
                for event, bound in admissible:
                    try:
                        problems.append(holds_during(run,
                            condition, run.index.bounds(event), bound, failures, episode,
                            f"step {step.id} ({event.id})",
                        ))
                    except Undetermined as error:
                        problems.append(unknown(error.kind, f"step {step.id}: {error.reason}"))
            for problem in problems:
                evidence.merge(problem.evidence)
            results.extend(problem for problem in problems if problem.outcome != "CLEAR")
            if not any(problem.outcome != "CLEAR" for problem in problems):
                results.append(Decision("CLEAR", f"step {step.id} observed ({admissible[0][0].id})"))
            continue
        if not step.required:
            results.append(Decision("CLEAR", f"optional step {step.id} not observed"))
        elif found:
            results.append(unknown("weak_evidence", f"step {step.id}: {run.weakness(found[0][0])}"))
        elif episode.end_boundary_status == "unknown":
            results.append(unknown("incomplete_episode",
                                    f"step {step.id} ({alternatives(step)}) not observed; the episode has no established end"))
        elif absent(step, bounds.latest_end) and episode.end_boundary_status == logic.end_boundary:
            results.append(Decision("VIOLATION", f"step {step.id} ({alternatives(step)}) did not happen",
                                    time=bounds.end))
        else:
            offcamera = step.omission_observability == "external_or_positively_verified_coverage"
            note = "it may happen off camera" if offcamera else "its absence is not proven"
            results.append(unknown("not_observed", f"step {step.id} ({alternatives(step)}) not observed; {note}",
                                    time=bounds.end))
    for constraint in logic.order_constraints:
        earlier, earlier_found = observed[constraint.before]
        later, _ = observed[constraint.after]
        if not later:
            continue
        first = later[0][0]
        closing = run.index.bounds(first)
        orders = [precedes(run.index.bounds(event), closing) for event, _ in earlier]
        label = f"{constraint.before} before {constraint.after} ({first.id})"
        if "TRUE" in orders:
            results.append(Decision("CLEAR", f"{label} holds"))
        elif "UNKNOWN" in orders or earlier_found > len(earlier):
            results.append(unknown("uncertain_order", f"{label} is uncertain"))
        elif absent(steps[constraint.before], closing.latest_start):
            results.append(Decision("VIOLATION", f"{label} was violated", time=first.time.start_sec))
        else:
            results.append(unknown("not_observed",
                                    f"{constraint.before} not observed before {constraint.after} ({first.id})",
                                    time=first.time.start_sec))
    details = [result.reason for result in results]
    for result in results:
        evidence.merge(result.evidence)
    violations = sorted((r for r in results if r.outcome == "VIOLATION"), key=lambda r: r.time or 0.0)
    if violations:
        return Decision("VIOLATION", "; ".join(r.reason for r in violations), time=violations[0].time,
                        span=violations[0].span, evidence=evidence, details=details)
    unknowns = [r for r in results if r.outcome == "UNKNOWN"]
    if unknowns:
        times = [r.time for r in unknowns if r.time is not None]
        kinds = [r.kind for r in unknowns]
        kind = "not_observed" if "not_observed" in kinds else kinds[0] or "uncertain_state"
        return unknown(kind, "; ".join(r.reason for r in unknowns),
                        time=min(times, default=None), evidence=evidence, details=details)
    return Decision("CLEAR", f"every step of episode {episode.id} conforms", evidence=evidence, details=details)


def _concurrency(
    intervals: list[tuple[float, float, str]], window: tuple[float, float]
) -> tuple[int, float, list[str]]:
    points = []
    for start, end, name in intervals:
        start, end = max(start, window[0]), min(end, window[1])
        if end > start + EPSILON:
            points.extend(((start, 1, name), (end, -1, name)))
    points.sort(key=lambda point: (point[0], point[1]))
    peak, moment, active, best = 0, window[0], set(), []
    for time, delta, name in points:
        if delta > 0:
            active.add(name)
        else:
            active.discard(name)
        if len(active) > peak:
            peak, moment, best = len(active), time, sorted(active)
    return peak, moment, best

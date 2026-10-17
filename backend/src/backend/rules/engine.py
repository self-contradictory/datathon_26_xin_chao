from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace

from backend.rules.findings import (
    EvaluationReport,
    Finding,
    FrameRef,
    Mode,
    Outcome,
    RuleEvaluation,
    UnknownKind,
)
from backend.rules.index import (
    EPSILON,
    Bounds,
    Evidence,
    Piece,
    STEGIndex,
    Truth,
    at_instant,
    conjunction,
    disjunction,
    precedes,
    relation_profile,
    sometime,
    state_profile,
    throughout,
)
from backend.rules.models import (
    EntityByEpisodeRole,
    EntityByKind,
    EpisodeEndMatcher,
    EpisodeMatcher,
    EventMatcher,
    Matcher,
    RelationMatcher,
    Rule,
    RuleRegistry,
    StateMatcher,
    VideoScope,
)
from backend.steg import Event, ProcedureEpisode, SparseTemporalEvidenceGraph, StateTrack

TRIGGER_ENTITY = "$trigger_entity"

type Quantifier = Callable[[Sequence[Piece]], Truth]
type Failures = dict[str, tuple[UnknownKind, str]]


class _Undetermined(Exception):
    def __init__(self, kind: UnknownKind, reason: str) -> None:
        super().__init__(reason)
        self.kind: UnknownKind = kind
        self.reason = reason


@dataclass(slots=True)
class _Context:

    episode: ProcedureEpisode | None
    window: tuple[float, float]
    values: dict[str, str]
    failures: Failures
    pool: list[Event]


@dataclass(slots=True)
class _Trigger:
    ref: str
    bounds: Bounds
    values: dict[str, str]
    failures: Failures
    evidence: Evidence
    weak: str | None = None
    event: Event | None = None
    episode: ProcedureEpisode | None = None


@dataclass(slots=True)
class _Check:
    truth: Truth
    reason: str
    kind: UnknownKind | None = None
    evidence: Evidence = field(default_factory=Evidence)
    values: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class _Verdict:
    outcome: Outcome
    reason: str
    kind: UnknownKind | None = None
    time: float | None = None
    span: tuple[float, float] | None = None
    evidence: Evidence = field(default_factory=Evidence)
    details: list[str] = field(default_factory=list)
    bindings: dict[str, str] = field(default_factory=dict)


def _unknown(kind: UnknownKind, reason: str, **extra) -> _Verdict:
    return _Verdict("UNKNOWN", reason, kind, **extra)


def _fmt(time: float) -> str:
    return f"{time:.1f}s"


def _first_kind(checks: Iterable[_Check]) -> tuple[UnknownKind, str]:
    for check in checks:
        if check.truth == "UNKNOWN":
            return check.kind or "uncertain_state", check.reason
    return "uncertain_state", "the evidence is inconclusive"


class _RuleRun:
    def __init__(self, rule: Rule, index: STEGIndex) -> None:
        self.rule = rule
        self.index = index
        self.policy = rule.evidence_policy


    def weakness(self, event: Event) -> str | None:
        if event.inference_status == "hypothesis" and not self.policy.allow_hypotheses:
            return f"event {event.id} ({event.action}) is only a hypothesis"
        if event.verification_status == "disputed" and not self.policy.allow_disputed:
            return f"event {event.id} ({event.action}) is disputed"
        return None

    def match(
        self, matcher: EventMatcher, event: Event, values: dict[str, str], failures: Failures
    ) -> tuple[dict[str, str], Failures] | None:
        if event.action != matcher.action:
            return None
        values, failures = dict(values), dict(failures)
        for role, variable in (matcher.participants or {}).items():
            holders = sorted({p.entity_id for p in event.participants if p.role == role})
            if variable in values:
                if values[variable] not in holders:
                    return None
                continue
            if not holders:
                failures.setdefault(
                    variable, ("missing_binding", f"event {event.id} has no {role} participant")
                )
            elif len(holders) > 1:
                failures[variable] = (
                    "ambiguous_role",
                    f"event {event.id} has {len(holders)} {role} participants",
                )
            elif self.index.entities[holders[0]].identity_status == "ambiguous":
                failures[variable] = (
                    "ambiguous_role",
                    f"{role} {holders[0]} of event {event.id} has an ambiguous identity",
                )
            else:
                values[variable] = holders[0]
                failures.pop(variable, None)
        return values, failures

    def occurrences(
        self,
        matcher: EventMatcher,
        pool: Iterable[Event],
        values: dict[str, str],
        failures: Failures,
        exclude: str | None = None,
    ) -> list[tuple[Event, dict[str, str]]]:
        found = []
        for event in pool:
            if event.id != exclude and (matched := self.match(matcher, event, values, failures)):
                found.append((event, matched[0]))
        return found

    def following(
        self,
        matcher: EventMatcher,
        trigger: _Trigger,
        pool: Iterable[Event],
    ) -> tuple[list[Event], list[Event]]:
        sure, doubtful = [], []
        for event, _ in self.occurrences(matcher, pool, trigger.values, trigger.failures, trigger.ref):
            order = precedes(trigger.bounds, self.index.bounds(event))
            if order == "FALSE":
                continue
            if order == "TRUE" and not self.weakness(event):
                sure.append(event)
            else:
                doubtful.append(event)
        def key(event: Event) -> tuple[float, str]:
            return self.index.bounds(event).earliest_start, event.id

        return sorted(sure, key=key), sorted(doubtful, key=key)

    def subjects(self, matcher: EventMatcher, values: dict[str, str]) -> list[str]:
        return [values[v] for v in (matcher.participants or {}).values() if v in values]

    def resolve(
        self,
        selector: str | EntityByKind | EntityByEpisodeRole,
        values: dict[str, str],
        failures: Failures,
        episode: ProcedureEpisode | None,
    ) -> list[str]:
        if isinstance(selector, str):
            if selector in values:
                return [values[selector]]
            kind, reason = failures.get(selector, ("missing_binding", f"{selector} is not bound"))
            raise _Undetermined(kind, f"{selector}: {reason}" if selector not in reason else reason)
        if isinstance(selector, EntityByKind):
            found = self.index.entities_of(selector.kind, selector.subtype)
            if not found:
                raise _Undetermined(
                    "missing_binding", f"no {selector.kind} entity of subtype {selector.subtype}"
                )
            return found
        role = selector.episode_role
        if episode is None:
            raise _Undetermined("missing_binding", f"episode role {role} used outside an episode")
        entity, problem = self.index.episode_role(episode, role)
        if entity is None:
            amount = "no" if problem == "missing_binding" else "more than one"
            raise _Undetermined(problem, f"episode {episode.id} has {amount} {role}")
        return [entity]

    def single(
        self,
        selector: str | EntityByKind | EntityByEpisodeRole,
        values: dict[str, str],
        failures: Failures,
        episode: ProcedureEpisode | None,
    ) -> str:
        entities = self.resolve(selector, values, failures, episode)
        if len(entities) != 1:
            raise _Undetermined("ambiguous_role", f"{len(entities)} entities match {selector}")
        return entities[0]

    def state_pieces(
        self, entity: str, matcher: StateMatcher, start: float, end: float
    ) -> tuple[StateTrack, list[Piece]]:
        tracks = self.index.state_tracks(entity, matcher.property)
        if not tracks:
            raise _Undetermined("no_track", f"the graph has no {matcher.property} track for {entity}")
        if len(tracks) > 1:
            raise _Undetermined(
                "uncertain_state", f"{len(tracks)} conflicting {matcher.property} tracks for {entity}"
            )
        return tracks[0], state_profile(tracks[0], start, end, matcher.value, matcher.knowledge)


    def condition(
        self,
        matcher: Matcher,
        values: dict[str, str],
        failures: Failures,
        episode: ProcedureEpisode | None,
        window: tuple[float, float],
        quantifier: Quantifier,
        pool: list[Event],
    ) -> _Check:
        try:
            match matcher:
                case StateMatcher():
                    return self._state_condition(matcher, values, failures, episode, window, quantifier)
                case RelationMatcher():
                    return self._relation_condition(matcher, values, failures, episode, window, quantifier)
                case EventMatcher():
                    return self._event_condition(matcher, values, failures, window, quantifier, pool)
                case EpisodeMatcher():
                    return self._episode_condition(matcher, window)
                case EpisodeEndMatcher():
                    raise _Undetermined("unsupported", "an episode end cannot be used as a condition")
        except _Undetermined as error:
            return _Check("UNKNOWN", error.reason, error.kind)

    def _state_condition(self, matcher, values, failures, episode, window, quantifier) -> _Check:
        checks = []
        for entity in self.resolve(matcher.entity, values, failures, episode):
            claim = f"{entity}.{matcher.property} = {matcher.value} over {_fmt(window[0])}–{_fmt(window[1])}"
            try:
                track, pieces = self.state_pieces(entity, matcher, *window)
            except _Undetermined as error:
                checks.append(_Check("UNKNOWN", error.reason, error.kind))
                continue
            truth = quantifier(pieces)
            evidence = Evidence()
            evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
            kind = None if truth != "UNKNOWN" else "uncertain_state"
            checks.append(_Check(truth, f"{claim}: {truth.lower()}", kind, evidence))
        return self._combine_existential(checks)

    def _combine_existential(self, checks: list[_Check]) -> _Check:
        truth = disjunction(check.truth for check in checks)
        chosen = [check for check in checks if check.truth == truth] or checks
        evidence = Evidence()
        for check in chosen:
            evidence.merge(check.evidence)
        values: dict[str, str] = {}
        for check in chosen:
            values.update(check.values)
        kind = _first_kind(checks)[0] if truth == "UNKNOWN" else None
        return _Check(truth, "; ".join(check.reason for check in chosen), kind, evidence, values)

    def _maybe_resolve(self, selector, values, failures, episode) -> list[str] | None:
        if isinstance(selector, str) and selector not in values and selector not in failures:
            return None
        return self.resolve(selector, values, failures, episode)

    def _relation_condition(self, matcher, values, failures, episode, window, quantifier) -> _Check:
        subjects = self._maybe_resolve(matcher.subject, values, failures, episode)
        targets = self._maybe_resolve(matcher.target, values, failures, episode)
        start, end = window
        relation = matcher.relation
        if subjects is None and targets is None:
            raise _Undetermined(
                "missing_binding", f"{matcher.subject} and {matcher.target} are both unbound"
            )
        checks: list[_Check] = []
        if subjects is None:
            for target in targets:
                holding = []
                for track in self.index.relation_tracks(relation):
                    pieces = relation_profile(track, start, end, target, matcher.knowledge)
                    if quantifier(pieces) == "TRUE":
                        holding.append((track, pieces))
                if len(holding) != 1:
                    kind = "missing_binding" if not holding else "ambiguous_role"
                    reason = f"{len(holding)} subjects are {relation} {target}"
                    checks.append(_Check("UNKNOWN", reason, kind))
                    continue
                track, pieces = holding[0]
                evidence = Evidence()
                evidence.add_pieces(track, pieces)
                checks.append(_Check(
                    "TRUE", f"{track.subject_id} {relation} {target}", None, evidence,
                    {matcher.subject: track.subject_id},
                ))
            return self._combine_existential(checks)
        for subject in subjects:
            tracks = self.index.relation_tracks(relation, subject)
            if len(tracks) != 1:
                kind = "no_track" if not tracks else "uncertain_state"
                checks.append(_Check("UNKNOWN", f"{len(tracks)} {relation} tracks for {subject}", kind))
                continue
            track = tracks[0]
            if targets is not None:
                for target in targets:
                    pieces = relation_profile(track, start, end, target, matcher.knowledge)
                    truth = quantifier(pieces)
                    evidence = Evidence()
                    evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
                    kind = None if truth != "UNKNOWN" else "uncertain_state"
                    checks.append(_Check(truth, f"{subject} {relation} {target}: {truth.lower()}", kind, evidence))
                continue
            pieces = relation_profile(track, start, end, None, matcher.knowledge)
            seen = sorted({p.target for p in pieces if p.status == "match" and p.target})
            holding = [
                target for target in seen
                if quantifier(relation_profile(track, start, end, target, matcher.knowledge)) == "TRUE"
            ]
            evidence = Evidence()
            evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
            if len(holding) == 1:
                checks.append(_Check(
                    "TRUE", f"{subject} {relation} {holding[0]}", None, evidence,
                    {matcher.target: holding[0]},
                ))
            elif len(holding) > 1:
                checks.append(_Check("UNKNOWN", f"{subject} is {relation} {len(holding)} targets", "ambiguous_role"))
            else:
                truth = "FALSE" if quantifier(pieces) == "FALSE" else "UNKNOWN"
                kind = None if truth == "FALSE" else "uncertain_state"
                checks.append(_Check(truth, f"{subject} {relation} anything: {truth.lower()}", kind, evidence))
        return self._combine_existential(checks)

    def _event_condition(self, matcher, values, failures, window, quantifier, pool) -> _Check:
        start, end = window
        weak = []
        for event, _ in self.occurrences(matcher, pool, values, failures):
            certain = self.index.bounds(event).certain
            if certain is None:
                continue
            covers = certain[0] <= start + EPSILON and certain[1] >= end - EPSILON
            overlaps = certain[0] <= end + EPSILON and certain[1] >= start - EPSILON
            if covers or (quantifier is sometime and overlaps):
                if reason := self.weakness(event):
                    weak.append(reason)
                    continue
                evidence = Evidence()
                evidence.add_event(event)
                return _Check("TRUE", f"{event.action} ({event.id}) is under way", None, evidence)
        absent, evidence = self.index.proven_absent(matcher.action, self.subjects(matcher, values), start, end)
        if absent:
            return _Check("FALSE", f"{matcher.action} provably not under way", None, evidence)
        if weak:
            return _Check("UNKNOWN", weak[0], "weak_evidence")
        return _Check("UNKNOWN", f"{matcher.action} not observed at {_fmt(start)}", "uncertain_state")

    def _episode_condition(self, matcher: EpisodeMatcher, window) -> _Check:
        for episode in self.index.episodes_of(matcher.episode_kind):
            bounds = self.index.episode_bounds(episode)
            if bounds.start <= window[0] + EPSILON and bounds.earliest_end >= window[1] - EPSILON:
                evidence = Evidence(episodes={episode.id})
                return _Check("TRUE", f"within {matcher.episode_kind} episode {episode.id}", None, evidence)
        return _Check("UNKNOWN", f"no {matcher.episode_kind} episode surely covers the moment", "uncertain_state")


    def contexts(self) -> list[_Context]:
        scope = self.rule.scope
        if isinstance(scope, VideoScope):
            pool = sorted(self.index.events.values(), key=lambda e: (e.time.start_sec, e.id))
            return [_Context(None, (0.0, self.index.duration), {}, {}, pool)]
        contexts = []
        for episode in self.index.episodes_of(scope.episode_kind):
            values = {scope.bind: episode.id}
            failures: Failures = {}
            for role, variable in (scope.episode_roles or {}).items():
                entity, problem = self.index.episode_role(episode, role)
                if entity is not None:
                    values[variable] = entity
                else:
                    amount = "no" if problem == "missing_binding" else "more than one"
                    failures[variable] = (problem, f"episode {episode.id} has {amount} {role}")
            bounds = self.index.episode_bounds(episode)
            window = (episode.start_sec, bounds.latest_end)
            contexts.append(_Context(episode, window, values, failures, self.index.members(episode)))
        return contexts

    def triggers(self, context: _Context) -> list[_Trigger]:
        trigger = self.rule.trigger
        try:
            match trigger:
                case EventMatcher():
                    return self._event_triggers(trigger, context)
                case StateMatcher():
                    return self._state_triggers(trigger, context)
                case RelationMatcher():
                    return self._relation_triggers(trigger, context)
                case EpisodeMatcher():
                    return self._episode_triggers(trigger, context)
                case EpisodeEndMatcher():
                    return self._episode_end_triggers(trigger, context)
        except _Undetermined:
            return []

    def _event_triggers(self, matcher: EventMatcher, context: _Context) -> list[_Trigger]:
        found = []
        for event in context.pool:
            matched = self.match(matcher, event, context.values, context.failures)
            if matched is None:
                continue
            evidence = Evidence()
            evidence.add_event(event)
            found.append(_Trigger(
                event.id, self.index.bounds(event), matched[0], matched[1], evidence,
                self.weakness(event), event=event,
            ))
        return found

    @staticmethod
    def _runs(pieces: list[Piece]) -> list[list[Piece]]:
        runs: list[list[Piece]] = []
        for piece in pieces:
            if piece.status != "match":
                continue
            if runs and piece.start <= runs[-1][-1].end + EPSILON:
                runs[-1].append(piece)
            else:
                runs.append([piece])
        return runs

    def _state_triggers(self, matcher: StateMatcher, context: _Context) -> list[_Trigger]:
        found = []
        entities = self.resolve(matcher.entity, context.values, context.failures, context.episode)
        for entity in entities:
            for track in self.index.state_tracks(entity, matcher.property):
                pieces = state_profile(track, *context.window, matcher.value, matcher.knowledge)
                for run in self._runs(pieces):
                    evidence = Evidence()
                    evidence.add_pieces(track, run)
                    values = context.values | {TRIGGER_ENTITY: entity}
                    if isinstance(matcher.entity, str):
                        values[matcher.entity] = entity
                    found.append(_Trigger(
                        track.id, Bounds.exact(run[0].start, run[-1].end), values,
                        dict(context.failures), evidence,
                    ))
        return found

    def _relation_triggers(self, matcher: RelationMatcher, context: _Context) -> list[_Trigger]:
        found = []
        subjects = self._maybe_resolve(matcher.subject, context.values, context.failures, context.episode)
        targets = self._maybe_resolve(matcher.target, context.values, context.failures, context.episode)
        tracks = [
            track for track in self.index.relation_tracks(matcher.relation)
            if subjects is None or track.subject_id in subjects
        ]
        for track in tracks:
            pieces = relation_profile(track, *context.window, None, matcher.knowledge)
            for target in sorted({p.target for p in pieces if p.status == "match" and p.target}):
                if targets is not None and target not in targets:
                    continue
                own = relation_profile(track, *context.window, target, matcher.knowledge)
                for run in self._runs(own):
                    evidence = Evidence()
                    evidence.add_pieces(track, run)
                    values = context.values | {TRIGGER_ENTITY: track.subject_id}
                    for selector, entity in ((matcher.subject, track.subject_id), (matcher.target, target)):
                        if isinstance(selector, str):
                            values[selector] = entity
                    found.append(_Trigger(
                        track.id, Bounds.exact(run[0].start, run[-1].end), values,
                        dict(context.failures), evidence,
                    ))
        return found

    def _episode_triggers(self, matcher: EpisodeMatcher, context: _Context) -> list[_Trigger]:
        if context.episode is not None and context.episode.kind == matcher.episode_kind:
            episodes = [context.episode]
        else:
            start, end = context.window
            episodes = [
                episode for episode in self.index.episodes_of(matcher.episode_kind)
                if episode.start_sec <= end and self.index.episode_bounds(episode).latest_end >= start
            ]
        found = []
        for episode in episodes:
            evidence = Evidence(episodes={episode.id}, observations=set(episode.basis_observation_ids))
            found.append(_Trigger(
                episode.id, self.index.episode_bounds(episode), dict(context.values),
                dict(context.failures), evidence, episode=episode,
            ))
        return found

    def _episode_end_triggers(self, matcher: EpisodeEndMatcher, context: _Context) -> list[_Trigger]:
        episodes = [context.episode] if context.episode else list(self.index.episodes.values())
        found = []
        for episode in sorted(episodes, key=lambda e: (e.start_sec, e.id)):
            if episode.end_boundary_status != matcher.requires_end_boundary or episode.end_sec is None:
                continue
            evidence = Evidence(episodes={episode.id}, observations=set(episode.basis_observation_ids))
            found.append(_Trigger(
                episode.id, Bounds.exact(episode.end_sec, episode.end_sec), dict(context.values),
                dict(context.failures), evidence, episode=episode,
            ))
        return found


    def _conjunctive(
        self,
        matchers: list[Matcher],
        context: _Context,
        trigger: _Trigger,
        window: tuple[float, float],
        quantifier: Quantifier,
        otherwise: Outcome,
    ) -> _Verdict:
        values, failures = dict(trigger.values), dict(trigger.failures)
        checks = []
        for matcher in matchers:
            check = self.condition(matcher, values, failures, context.episode, window, quantifier, context.pool)
            values.update(check.values)
            checks.append(check)
        evidence = Evidence()
        for check in checks:
            evidence.merge(check.evidence)
        details = [check.reason for check in checks]
        truth = conjunction(check.truth for check in checks)
        if truth == "TRUE":
            reason = "every condition held" if checks else "the trigger itself is prohibited"
            return _Verdict("VIOLATION", f"{reason}: " + "; ".join(details) if details else reason,
                            time=trigger.bounds.start, evidence=evidence, details=details, bindings=values)
        if truth == "FALSE":
            failed = next(check for check in checks if check.truth == "FALSE")
            return _Verdict(otherwise, f"condition not met: {failed.reason}", evidence=evidence,
                            details=details, bindings=values)
        kind, reason = _first_kind(checks)
        return _unknown(kind, reason, evidence=evidence, details=details, bindings=values)

    def _forbidden(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        return self._conjunctive(logic.when_all, context, trigger, trigger.bounds.start_window, at_instant, "CLEAR")

    def _role_relation(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        return self._conjunctive(logic.all_of, context, trigger, trigger.bounds.start_window, at_instant, "CLEAR")

    def _conditional(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        window = trigger.bounds.certain or trigger.bounds.start_window
        return self._conjunctive(logic.if_all, context, trigger, window, sometime, "NOT_APPLICABLE")

    def _holds_during(
        self,
        matcher: StateMatcher,
        bounds: Bounds,
        values: dict[str, str],
        failures: Failures,
        episode: ProcedureEpisode | None,
        label: str,
    ) -> _Verdict:
        entity = self.single(matcher.entity, values, failures, episode)
        claim = f"{entity}.{matcher.property} = {matcher.value}"
        track, pieces = self.state_pieces(entity, matcher, *bounds.possible)
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
            return _Verdict(
                "VIOLATION",
                f"{claim} was contradicted from {_fmt(first.start)} while {label}",
                time=first.start, span=(first.start, inside[-1].end), evidence=evidence,
            )
        if throughout(pieces) == "TRUE":
            evidence.add_pieces(track, pieces)
            return _Verdict("CLEAR", f"{claim} held throughout {label}", evidence=evidence)
        margin = any(p.status == "contradict" for p in pieces)
        evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
        reason = (
            f"{claim} was contradicted only where the timing of {label} is uncertain"
            if margin else f"{claim} is not established throughout {label}"
        )
        return _unknown("uncertain_order" if margin else "uncertain_state", reason, evidence=evidence)

    def _during(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        action = trigger.event.action if trigger.event else "the trigger"
        label = f"{action} ({trigger.ref})"
        return self._holds_during(logic.required, trigger.bounds, trigger.values, trigger.failures, context.episode, label)

    def _state_invariant(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        sure, doubtful = self.following(logic.until, trigger, context.pool)
        end_sure = end_maybe = context.window[1]
        boundary = f"the end of the {'episode' if context.episode else 'video'}"
        if sure:
            until = self.index.bounds(sure[0])
            end_sure, end_maybe = until.earliest_start, until.latest_start
            boundary = f"{sure[0].action} ({sure[0].id})"
        if doubtful:
            end_sure = min(end_sure, min(self.index.bounds(e).earliest_start for e in doubtful))
        start_sure, start_maybe = trigger.bounds.latest_end, trigger.bounds.earliest_end
        entity = self.single(logic.required.entity, trigger.values, trigger.failures, context.episode)
        claim = f"{entity}.{logic.required.property} = {logic.required.value}"
        evidence = Evidence()
        if end_sure > start_sure + EPSILON:
            track, pieces = self.state_pieces(entity, logic.required, start_sure, end_sure)
            breaches = [p for p in pieces if p.status == "contradict"]
            if breaches:
                evidence.add_pieces(track, breaches)
                return _Verdict(
                    "VIOLATION",
                    f"{claim} was broken at {_fmt(breaches[0].start)}, before {boundary}",
                    time=breaches[0].start, span=(breaches[0].start, breaches[-1].end), evidence=evidence,
                )
        track, pieces = self.state_pieces(entity, logic.required, start_maybe, max(start_maybe, end_maybe))
        evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
        if throughout(pieces) == "TRUE":
            return _Verdict("CLEAR", f"{claim} held until {boundary}", evidence=evidence)
        return _unknown("uncertain_state", f"{claim} is not established until {boundary}", evidence=evidence)

    def _required_action(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        episode = context.episode or self._episode_of(trigger)
        if episode is None:
            raise _Undetermined("missing_binding", "no procedure episode contains the trigger")
        members = self.index.members(episode)
        sure, doubtful = self.following(logic.must, trigger, members)
        evidence = Evidence(episodes={episode.id})
        if sure:
            evidence.add_event(sure[0])
            return _Verdict("CLEAR", f"{logic.must.action} ({sure[0].id}) followed the trigger",
                            time=sure[0].time.start_sec, evidence=evidence)
        if doubtful:
            event = doubtful[0]
            evidence.add_event(event)
            weak = self.weakness(event)
            return _unknown("weak_evidence" if weak else "uncertain_order",
                            weak or f"the order of {event.id} and the trigger is uncertain", evidence=evidence)
        deadline = self.index.episode_bounds(episode)
        outside, _ = self.following(logic.must, trigger, [e for e in self.index.events.values() if e.id not in episode.event_ids])
        outside = [e for e in outside if e.time.start_sec <= deadline.latest_end]
        if outside:
            evidence.add_event(outside[0])
            return _unknown("uncertain_order", f"{outside[0].id} matches but is not part of episode {episode.id}",
                            evidence=evidence)
        if episode.end_boundary_status == "unknown":
            return _unknown("incomplete_episode", f"episode {episode.id} has no established end", evidence=evidence)
        window = (trigger.bounds.earliest_start, deadline.latest_end)
        absent, proof = self.index.proven_absent(logic.must.action, self.subjects(logic.must, trigger.values), *window)
        evidence.merge(proof)
        end = deadline.end
        missing = f"{logic.must.action} not observed between the trigger and the episode end at {_fmt(end)}"
        if absent and episode.end_boundary_status == logic.deadline.requires_end_boundary:
            return _Verdict("VIOLATION", f"{missing}; an activity track shows it did not happen",
                            time=end, span=(trigger.bounds.start, end), evidence=evidence)
        detail = "the episode end is only inferred" if absent else "its absence is not proven"
        return _unknown("not_observed", f"{missing}; {detail}", time=end, evidence=evidence)

    def _episode_of(self, trigger: _Trigger) -> ProcedureEpisode | None:
        if trigger.episode is not None:
            return trigger.episode
        owners = sorted(self.index.event_episodes.get(trigger.ref, set()))
        return self.index.episodes[owners[0]] if len(owners) == 1 else None

    def _precedence(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        boundaries, doubtful_boundaries = self.following(logic.before, trigger, context.pool)
        required, doubtful_required = self.following(logic.must_precede, trigger, context.pool)
        evidence = Evidence()
        if not boundaries:
            if required:
                evidence.add_event(required[0])
                return _Verdict("CLEAR", f"{logic.must_precede.action} ({required[0].id}) followed the trigger",
                                time=required[0].time.start_sec, evidence=evidence)
            if doubtful_boundaries:
                evidence.add_event(doubtful_boundaries[0])
                return _unknown("uncertain_order", f"{doubtful_boundaries[0].id} may close the window", evidence=evidence)
            return _Verdict("NOT_APPLICABLE", f"no {logic.before.action} observed after the trigger")
        boundary = boundaries[0]
        closing = self.index.bounds(boundary)
        evidence.add_event(boundary)
        for event in required:
            if precedes(self.index.bounds(event), closing) == "TRUE":
                evidence.add_event(event)
                return _Verdict("CLEAR", f"{logic.must_precede.action} ({event.id}) came before {boundary.id}",
                                time=event.time.start_sec, evidence=evidence)
        pending = [e for e in required + doubtful_required if precedes(self.index.bounds(e), closing) != "FALSE"]
        if pending:
            evidence.add_event(pending[0])
            weak = self.weakness(pending[0])
            return _unknown("weak_evidence" if weak else "uncertain_order",
                            weak or f"the order of {pending[0].id} and {boundary.id} is uncertain", evidence=evidence)
        window = (trigger.bounds.earliest_start, closing.latest_end)
        absent, proof = self.index.proven_absent(
            logic.must_precede.action, self.subjects(logic.must_precede, trigger.values), *window
        )
        evidence.merge(proof)
        missing = f"{logic.must_precede.action} not observed before {logic.before.action} ({boundary.id}) at {_fmt(boundary.time.start_sec)}"
        if absent:
            return _Verdict("VIOLATION", f"{missing}; an activity track shows it did not happen",
                            time=boundary.time.start_sec, span=(trigger.bounds.start, boundary.time.start_sec),
                            evidence=evidence)
        return _unknown("not_observed", f"{missing}; its absence is not proven",
                        time=boundary.time.start_sec, evidence=evidence)

    def _timeout(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        limit = logic.within_seconds
        earliest, latest = trigger.bounds.end_window
        evidence = Evidence()
        doubtful = []
        for event, _ in self.occurrences(logic.must, context.pool, trigger.values, trigger.failures, trigger.ref):
            bounds = self.index.bounds(event)
            if precedes(bounds, trigger.bounds) == "TRUE":
                continue
            if not self.weakness(event) and bounds.latest_start <= earliest + limit + EPSILON:
                evidence.add_event(event)
                return _Verdict("CLEAR", f"{event.action} ({event.id}) came within {limit:g}s",
                                time=event.time.start_sec, evidence=evidence)
            if bounds.earliest_start <= latest + limit + EPSILON:
                doubtful.append(event)
        deadline = min(trigger.bounds.end + limit, self.index.duration)
        if doubtful:
            evidence.add_event(doubtful[0])
            weak = self.weakness(doubtful[0])
            return _unknown("weak_evidence" if weak else "uncertain_order",
                            weak or f"{doubtful[0].id} may fall inside the {limit:g}s limit", evidence=evidence)
        if latest + limit > self.index.duration + EPSILON:
            return _unknown("incomplete_episode", f"the {limit:g}s deadline falls after the video ends")
        absent, proof = self.index.proven_absent(
            logic.must.action, self.subjects(logic.must, trigger.values), earliest, latest + limit
        )
        evidence.merge(proof)
        missing = f"{logic.must.action} not observed within {limit:g}s of the trigger ending"
        if absent:
            return _Verdict("VIOLATION", f"{missing}; an activity track shows it did not happen",
                            time=deadline, span=(trigger.bounds.end, deadline), evidence=evidence)
        return _unknown("not_observed", f"{missing}; its absence is not proven", time=deadline, evidence=evidence)

    def _mutual_exclusion(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        other = logic.other
        certain = trigger.bounds.certain
        span = certain or trigger.bounds.possible
        checks: list[_Check] = []
        for entity in self.resolve(other.entity, trigger.values, trigger.failures, context.episode):
            claim = f"{entity}.{other.property} = {other.value}"
            try:
                track, pieces = self.state_pieces(entity, other, *span)
            except _Undetermined as error:
                checks.append(_Check("UNKNOWN", error.reason, error.kind))
                continue
            overlap = self._runs(pieces)
            evidence = Evidence()
            if overlap and certain is not None:
                run = overlap[0]
                evidence.add_pieces(track, run)
                return _Verdict(
                    "VIOLATION", f"{claim} overlapped the trigger from {_fmt(run[0].start)} to {_fmt(run[-1].end)}",
                    time=run[0].start, span=(run[0].start, run[-1].end), evidence=evidence,
                )
            evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
            if overlap:
                checks.append(_Check("UNKNOWN", f"{claim} may overlap the trigger", "uncertain_order", evidence))
            elif sometime(pieces) == "FALSE":
                checks.append(_Check("FALSE", f"{claim} did not hold during the trigger", None, evidence))
            else:
                checks.append(_Check("UNKNOWN", f"{claim} is not established during the trigger", "uncertain_state", evidence))
        evidence = Evidence()
        for check in checks:
            evidence.merge(check.evidence)
        if checks and all(check.truth == "FALSE" for check in checks):
            return _Verdict("CLEAR", "; ".join(check.reason for check in checks), evidence=evidence)
        kind, reason = _first_kind(checks)
        return _unknown(kind, reason, evidence=evidence)

    def _cardinality(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        source = logic.cashier_from

        def cashier(episode: ProcedureEpisode) -> tuple[str | None, UnknownKind]:
            holders = {
                p.entity_id
                for event in self.index.members(episode)
                if event.action == source.event_action and not self.weakness(event)
                for p in event.participants if p.role == source.participant_role
            }
            if len(holders) == 1:
                return next(iter(holders)), "missing_binding"
            return None, "missing_binding" if not holders else "ambiguous_role"

        own, problem = cashier(trigger.episode)
        if own is None:
            raise _Undetermined(problem, f"episode {trigger.episode.id} has no single {source.participant_role}")
        bounds = trigger.bounds
        window = (bounds.start, bounds.latest_end)
        counted = set(trigger.episode.event_ids)
        sure = [(bounds.start, bounds.earliest_end, trigger.episode.id)]
        maybe = [(bounds.start, bounds.latest_end, trigger.episode.id)]
        evidence = Evidence(episodes={trigger.episode.id})
        for other in self.index.episodes_of(logic.count.episode_kind):
            if other.id == trigger.episode.id or counted & set(other.event_ids):
                continue
            other_bounds = self.index.episode_bounds(other)
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
            return _Verdict(
                "VIOLATION", f"{own} had {peak} {logic.count.episode_kind} episodes open at {_fmt(moment)} "
                f"({', '.join(active)}); the limit is {limit}", time=moment, evidence=evidence,
            )
        possible, moment, active = _concurrency(maybe, window)
        if possible > limit:
            return _unknown("uncertain_order", f"up to {possible} episodes may overlap at {_fmt(moment)} "
                            f"({', '.join(active)}); cashier or end not established", evidence=evidence)
        return _Verdict("CLEAR", f"at most {peak} {logic.count.episode_kind} episode open at once", evidence=evidence)

    def _separation(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        matcher = self.rule.trigger
        origin = logic.origin
        evidence = Evidence()
        origins: dict[str, str] = {}
        for role, variable in (matcher.participants or {}).items():
            if variable not in trigger.values:
                kind, reason = trigger.failures.get(variable, ("missing_binding", f"{variable} is not bound"))
                raise _Undetermined(kind, reason)
            item = trigger.values[variable]
            if self.index.entities[item].identity_status == "ambiguous":
                raise _Undetermined("ambiguous_role", f"{role} {item} has an ambiguous identity")
            sure, doubtful = set(), set()
            for episode in self.index.episodes.values():
                for event in self.index.members(episode):
                    if event.action == origin.event_action and any(
                        p.role == origin.bundle_participant_role and p.entity_id == item for p in event.participants
                    ):
                        (doubtful if self.weakness(event) else sure).add(episode.id)
                        evidence.add_event(event)
            if not sure:
                kind = "weak_evidence" if doubtful else "missing_binding"
                raise _Undetermined(kind, f"the origin episode of {item} is not established")
            if len(sure) > 1 or doubtful - sure:
                raise _Undetermined("ambiguous_role", f"{item} traces to {len(sure | doubtful)} episodes")
            origins[item] = next(iter(sure))
        evidence.episodes.update(origins.values())
        trail = ", ".join(f"{item} from {episode}" for item, episode in origins.items())
        if len(set(origins.values())) > 1:
            return _Verdict("VIOLATION", f"items from different procedures were merged: {trail}",
                            time=trigger.bounds.start, evidence=evidence)
        return _Verdict("CLEAR", f"all merged items come from one procedure: {trail}", evidence=evidence)

    def _procedure(self, context: _Context, trigger: _Trigger) -> _Verdict:
        logic = self.rule.logic
        episode = context.episode
        members = self.index.members(episode)
        bounds = self.index.episode_bounds(episode)
        values, failures = context.values, context.failures
        evidence = Evidence(episodes={episode.id})
        results: list[_Verdict] = []
        observed: dict[str, tuple[list[tuple[Event, dict[str, str]]], int]] = {}
        steps = {step.id: step for step in logic.steps}

        def absent(step, end: float) -> bool:
            verified = step.omission_observability is not None
            for alternative in step.any_of:
                proven, proof = self.index.proven_absent(
                    alternative.action, self.subjects(alternative, values), episode.start_sec, end, verified=verified
                )
                if not proven:
                    return False
                evidence.merge(proof)
            return True

        def alternatives(step) -> str:
            return " or ".join(alternative.action for alternative in step.any_of)

        for step in logic.steps:
            found = [o for alternative in step.any_of for o in self.occurrences(alternative, members, values, failures)]
            admissible = [(event, bound) for event, bound in found if not self.weakness(event)]
            observed[step.id] = (sorted(admissible, key=lambda o: self.index.bounds(o[0]).earliest_start), len(found))
            if admissible:
                for event, _ in admissible:
                    evidence.add_event(event)
                problems = []
                for condition in step.while_ or []:
                    for event, bound in admissible:
                        try:
                            problems.append(self._holds_during(
                                condition, self.index.bounds(event), bound, failures, episode,
                                f"step {step.id} ({event.id})",
                            ))
                        except _Undetermined as error:
                            problems.append(_unknown(error.kind, f"step {step.id}: {error.reason}"))
                for problem in problems:
                    evidence.merge(problem.evidence)
                results.extend(problem for problem in problems if problem.outcome != "CLEAR")
                if not any(problem.outcome != "CLEAR" for problem in problems):
                    results.append(_Verdict("CLEAR", f"step {step.id} observed ({admissible[0][0].id})"))
                continue
            if not step.required:
                results.append(_Verdict("CLEAR", f"optional step {step.id} not observed"))
            elif found:
                results.append(_unknown("weak_evidence", f"step {step.id}: {self.weakness(found[0][0])}"))
            elif episode.end_boundary_status == "unknown":
                results.append(_unknown("incomplete_episode",
                                        f"step {step.id} ({alternatives(step)}) not observed; the episode has no established end"))
            elif absent(step, bounds.latest_end) and episode.end_boundary_status == logic.end_boundary:
                results.append(_Verdict("VIOLATION", f"step {step.id} ({alternatives(step)}) did not happen",
                                        time=bounds.end))
            else:
                offcamera = step.omission_observability == "external_or_positively_verified_coverage"
                note = "it may happen off camera" if offcamera else "its absence is not proven"
                results.append(_unknown("not_observed", f"step {step.id} ({alternatives(step)}) not observed; {note}",
                                        time=bounds.end))
        for constraint in logic.order_constraints:
            earlier, earlier_found = observed[constraint.before]
            later, _ = observed[constraint.after]
            if not later:
                continue
            first = later[0][0]
            closing = self.index.bounds(first)
            orders = [precedes(self.index.bounds(event), closing) for event, _ in earlier]
            label = f"{constraint.before} before {constraint.after} ({first.id})"
            if "TRUE" in orders:
                results.append(_Verdict("CLEAR", f"{label} holds"))
            elif "UNKNOWN" in orders or earlier_found > len(earlier):
                results.append(_unknown("uncertain_order", f"{label} is uncertain"))
            elif absent(steps[constraint.before], closing.latest_start):
                results.append(_Verdict("VIOLATION", f"{label} was violated", time=first.time.start_sec))
            else:
                results.append(_unknown("not_observed",
                                        f"{constraint.before} not observed before {constraint.after} ({first.id})",
                                        time=first.time.start_sec))
        details = [result.reason for result in results]
        for result in results:
            evidence.merge(result.evidence)
        violations = sorted((r for r in results if r.outcome == "VIOLATION"), key=lambda r: r.time or 0.0)
        if violations:
            return _Verdict("VIOLATION", "; ".join(r.reason for r in violations), time=violations[0].time,
                            span=violations[0].span, evidence=evidence, details=details)
        unknowns = [r for r in results if r.outcome == "UNKNOWN"]
        if unknowns:
            times = [r.time for r in unknowns if r.time is not None]
            kinds = [r.kind for r in unknowns]
            kind = "not_observed" if "not_observed" in kinds else kinds[0] or "uncertain_state"
            return _unknown(kind, "; ".join(r.reason for r in unknowns),
                            time=min(times, default=None), evidence=evidence, details=details)
        return _Verdict("CLEAR", f"every step of episode {episode.id} conforms", evidence=evidence, details=details)

    EVALUATORS: dict[str, Callable[[_RuleRun, _Context, _Trigger], _Verdict]] = {
        "FORBIDDEN": _forbidden,
        "REQUIRED_ACTION": _required_action,
        "PRECEDENCE": _precedence,
        "DURING": _during,
        "STATE_INVARIANT": _state_invariant,
        "CONDITIONAL": _conditional,
        "TIMEOUT": _timeout,
        "CARDINALITY": _cardinality,
        "MUTUAL_EXCLUSION": _mutual_exclusion,
        "ROLE_RELATION": _role_relation,
        "SEPARATION": _separation,
        "PROCEDURE": _procedure,
    }


    def run(self) -> list[Finding]:
        findings = []
        for context in self.contexts():
            triggers = self.triggers(context)
            if self.rule.type == "PROCEDURE":
                triggers = triggers[:1]
            for trigger in triggers:
                findings.append(self.finding(context, trigger, self.decide(context, trigger)))
        return findings

    def decide(self, context: _Context, trigger: _Trigger) -> _Verdict:
        try:
            verdict = self.EVALUATORS[self.rule.logic.type](self, context, trigger)
        except _Undetermined as error:
            verdict = _unknown(error.kind, error.reason)
        if verdict.outcome == "VIOLATION" and trigger.weak:
            verdict = replace(verdict, outcome="UNKNOWN", kind="weak_evidence",
                              reason=f"{verdict.reason}, but {trigger.weak}")
        return verdict

    def finding(self, context: _Context, trigger: _Trigger, verdict: _Verdict) -> Finding:
        evidence = Evidence()
        evidence.merge(trigger.evidence)
        evidence.merge(verdict.evidence)
        if context.episode is not None:
            evidence.episodes.add(context.episode.id)
        references = (
            evidence.events | evidence.state_tracks | evidence.relation_tracks
            | evidence.episodes | set(trigger.values.values())
        )
        flags = self.index.flags_for(references)
        outcome, kind, reason = verdict.outcome, verdict.kind, verdict.reason
        critical = [flag for flag in flags if flag.severity == "critical"]
        if outcome == "VIOLATION" and critical:
            outcome, kind = "UNKNOWN", "critical_quality_flag"
            reason = f"{reason}; critical quality flag {critical[0].id}: {critical[0].note}"
        time = verdict.time if verdict.time is not None else trigger.bounds.start
        start, end = verdict.span or (trigger.bounds.start, trigger.bounds.end)
        rule = self.rule
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
            evidence_frames=self.frames(evidence, time), source=rule.source,
        )

    def frames(self, evidence: Evidence, time: float) -> list[FrameRef]:
        limit = self.policy.max_evidence_frames
        candidates = self.index.frames_for(evidence) or self.index.nearest_frames(time, limit)
        chosen = sorted(candidates.items(), key=lambda item: (abs(item[1] - time), item[1], item[0]))[:limit]
        return [FrameRef(id=frame, timestamp_sec=moment) for frame, moment in sorted(chosen, key=lambda i: (i[1], i[0]))]


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


def evaluate_rule(rule: Rule, index: STEGIndex) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule.rule_id, version=rule.version, status=rule.status, type=rule.type,
        findings=_RuleRun(rule, index).run(),
    )


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

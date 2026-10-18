from collections.abc import Iterable

from backend.rules.evaluation import (
    Check,
    Failures,
    Quantifier,
    Trigger,
    Undetermined,
    first_unknown,
    format_time,
)
from backend.rules.index import (
    EPSILON,
    Evidence,
    Piece,
    STEGIndex,
    disjunction,
    precedes,
    relation_profile,
    sometime,
    state_profile,
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
    StateMatcher,
)
from backend.steg import Event, ProcedureEpisode, StateTrack


class RuleMatcher:
    def __init__(self, rule: Rule, index: STEGIndex) -> None:
        self.rule = rule
        self.index = index
        self.policy = rule.evidence_policy

    def weakness(self, event: Event) -> str | None:
        if self.policy.required_verification and event.verification_status != self.policy.required_verification:
            return f"event {event.id} requires {self.policy.required_verification} evidence"
        if event.inference_status == "hypothesis" and not self.policy.allow_hypotheses:
            return f"event {event.id} ({event.action}) is only a hypothesis"
        if event.verification_status == "disputed" and not self.policy.allow_disputed:
            return f"event {event.id} ({event.action}) is disputed"
        return None

    def match(
        self, matcher: EventMatcher, event: Event, values: dict[str, str], failures: Failures
    ) -> tuple[dict[str, str], Failures] | None:
        if not self.index.action_matches(event, matcher.action):
            return None
        values, failures = dict(values), dict(failures)
        for role, variable in (matcher.participants or {}).items():
            holders = sorted({p.entity_id for p in event.participants
                              if self.index.supports("role", event.id, p.role, role)})
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
        trigger: Trigger,
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
            raise Undetermined(kind, f"{selector}: {reason}" if selector not in reason else reason)
        if isinstance(selector, EntityByKind):
            found = self.index.entities_of(selector.kind, selector.subtype)
            if not found:
                raise Undetermined(
                    "missing_binding", f"no {selector.kind} entity of subtype {selector.subtype}"
                )
            return found
        role = selector.episode_role
        if episode is None:
            raise Undetermined("missing_binding", f"episode role {role} used outside an episode")
        entity, problem = self.index.episode_role(episode, role)
        if entity is None:
            amount = "no" if problem == "missing_binding" else "more than one"
            raise Undetermined(problem, f"episode {episode.id} has {amount} {role}")
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
            raise Undetermined("ambiguous_role", f"{len(entities)} entities match {selector}")
        return entities[0]

    def state_pieces(
        self, entity: str, matcher: StateMatcher, start: float, end: float
    ) -> tuple[StateTrack, list[Piece]]:
        tracks = self.index.state_tracks(entity, matcher.property)
        if not tracks:
            raise Undetermined("no_track", f"the graph has no {matcher.property} track for {entity}")
        if len(tracks) > 1:
            raise Undetermined(
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
    ) -> Check:
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
                    raise Undetermined("unsupported", "an episode end cannot be used as a condition")
        except Undetermined as error:
            return Check("UNKNOWN", error.reason, error.kind)

    def _state_condition(self, matcher, values, failures, episode, window, quantifier) -> Check:
        checks = []
        for entity in self.resolve(matcher.entity, values, failures, episode):
            claim = f"{entity}.{matcher.property} = {matcher.value} over {format_time(window[0])}–{format_time(window[1])}"
            try:
                track, pieces = self.state_pieces(entity, matcher, *window)
            except Undetermined as error:
                checks.append(Check("UNKNOWN", error.reason, error.kind))
                continue
            truth = quantifier(pieces)
            evidence = Evidence()
            evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
            kind = None if truth != "UNKNOWN" else "uncertain_state"
            checks.append(Check(truth, f"{claim}: {truth.lower()}", kind, evidence))
        return self._combine_existential(checks)

    def _combine_existential(self, checks: list[Check]) -> Check:
        truth = disjunction(check.truth for check in checks)
        chosen = [check for check in checks if check.truth == truth] or checks
        evidence = Evidence()
        for check in chosen:
            evidence.merge(check.evidence)
        values: dict[str, str] = {}
        for check in chosen:
            values.update(check.values)
        kind = first_unknown(checks)[0] if truth == "UNKNOWN" else None
        return Check(truth, "; ".join(check.reason for check in chosen), kind, evidence, values)

    def maybe_resolve(self, selector, values, failures, episode) -> list[str] | None:
        if isinstance(selector, str) and selector not in values and selector not in failures:
            return None
        return self.resolve(selector, values, failures, episode)

    def _relation_condition(self, matcher, values, failures, episode, window, quantifier) -> Check:
        subjects = self.maybe_resolve(matcher.subject, values, failures, episode)
        targets = self.maybe_resolve(matcher.target, values, failures, episode)
        start, end = window
        relation = matcher.relation
        if subjects is None and targets is None:
            raise Undetermined(
                "missing_binding", f"{matcher.subject} and {matcher.target} are both unbound"
            )
        checks: list[Check] = []
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
                    checks.append(Check("UNKNOWN", reason, kind))
                    continue
                track, pieces = holding[0]
                evidence = Evidence()
                evidence.add_pieces(track, pieces)
                checks.append(Check(
                    "TRUE", f"{track.subject_id} {relation} {target}", None, evidence,
                    {matcher.subject: track.subject_id},
                ))
            return self._combine_existential(checks)
        for subject in subjects:
            tracks = self.index.relation_tracks(relation, subject)
            if len(tracks) != 1:
                kind = "no_track" if not tracks else "uncertain_state"
                checks.append(Check("UNKNOWN", f"{len(tracks)} {relation} tracks for {subject}", kind))
                continue
            track = tracks[0]
            if targets is not None:
                for target in targets:
                    pieces = relation_profile(track, start, end, target, matcher.knowledge)
                    truth = quantifier(pieces)
                    evidence = Evidence()
                    evidence.add_pieces(track, [p for p in pieces if p.status != "unknown"])
                    kind = None if truth != "UNKNOWN" else "uncertain_state"
                    checks.append(Check(truth, f"{subject} {relation} {target}: {truth.lower()}", kind, evidence))
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
                checks.append(Check(
                    "TRUE", f"{subject} {relation} {holding[0]}", None, evidence,
                    {matcher.target: holding[0]},
                ))
            elif len(holding) > 1:
                checks.append(Check("UNKNOWN", f"{subject} is {relation} {len(holding)} targets", "ambiguous_role"))
            else:
                truth = "FALSE" if quantifier(pieces) == "FALSE" else "UNKNOWN"
                kind = None if truth == "FALSE" else "uncertain_state"
                checks.append(Check(truth, f"{subject} {relation} anything: {truth.lower()}", kind, evidence))
        return self._combine_existential(checks)

    def _event_condition(self, matcher, values, failures, window, quantifier, pool) -> Check:
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
                return Check("TRUE", f"{event.action} ({event.id}) is under way", None, evidence)
        absent, evidence = self.index.proven_absent(matcher.action, self.subjects(matcher, values), start, end)
        if absent:
            return Check("FALSE", f"{matcher.action} provably not under way", None, evidence)
        if weak:
            return Check("UNKNOWN", weak[0], "weak_evidence")
        return Check("UNKNOWN", f"{matcher.action} not observed at {format_time(start)}", "uncertain_state")

    def _episode_condition(self, matcher: EpisodeMatcher, window) -> Check:
        for episode in self.index.episodes_of(matcher.episode_kind):
            bounds = self.index.episode_bounds(episode)
            if bounds.start <= window[0] + EPSILON and bounds.earliest_end >= window[1] - EPSILON:
                evidence = Evidence(episodes={episode.id})
                return Check("TRUE", f"within {matcher.episode_kind} episode {episode.id}", None, evidence)
        return Check("UNKNOWN", f"no {matcher.episode_kind} episode surely covers the moment", "uncertain_state")

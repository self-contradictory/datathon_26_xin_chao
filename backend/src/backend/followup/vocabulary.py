from collections import defaultdict

from pydantic import BaseModel

from backend.rules.models import (
    EntityByKind, EpisodeMatcher, EventMatcher, RelationMatcher, Rule, StateMatcher,
)


def matchers(value):
    if isinstance(value, (EventMatcher, StateMatcher, RelationMatcher, EpisodeMatcher)):
        yield value
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from matchers(getattr(value, name))
    elif isinstance(value, list):
        for item in value:
            yield from matchers(item)


def vocabulary(rules: list[Rule]) -> dict[str, list[str]]:
    terms = defaultdict(set)
    for rule in rules:
        if rule.scope.kind == "episode":
            terms["episode"].add(rule.scope.episode_kind)
            terms["role"].update((rule.scope.episode_roles or {}).keys())
        for matcher in matchers(rule):
            if isinstance(matcher, EventMatcher):
                terms["action"].add(matcher.action)
                terms["role"].update((matcher.participants or {}).keys())
            elif isinstance(matcher, StateMatcher):
                terms["state"].add(matcher.property)
            elif isinstance(matcher, RelationMatcher):
                terms["relation"].add(matcher.relation)
            elif isinstance(matcher, EpisodeMatcher):
                terms["episode"].add(matcher.episode_kind)
            for name in ("entity", "subject", "target"):
                selector = getattr(matcher, name, None)
                if isinstance(selector, EntityByKind):
                    terms["entity"].add(selector.subtype)
        if rule.type == "CARDINALITY":
            terms["action"].add(rule.logic.cashier_from.event_action)
            terms["role"].add(rule.logic.cashier_from.participant_role)
        if rule.type == "SEPARATION":
            terms["action"].add(rule.logic.origin.event_action)
            terms["role"].add(rule.logic.origin.bundle_participant_role)
    return {kind: sorted(values) for kind, values in terms.items()}

from backend.rules.evaluation import Context, Failures, TRIGGER_ENTITY, Trigger, Undetermined
from backend.rules.index import (
    Bounds,
    Evidence,
    matching_runs,
    relation_profile,
    state_profile,
)
from backend.rules.matching import RuleMatcher
from backend.rules.models import (
    EpisodeEndMatcher,
    EpisodeMatcher,
    EventMatcher,
    RelationMatcher,
    StateMatcher,
    VideoScope,
)


def contexts(run: RuleMatcher) -> list[Context]:
    scope = run.rule.scope
    if isinstance(scope, VideoScope):
        pool = sorted(run.index.events.values(), key=lambda e: (e.time.start_sec, e.id))
        return [Context(None, (0.0, run.index.duration), {}, {}, pool)]
    contexts = []
    for episode in run.index.episodes_of(scope.episode_kind):
        values = {scope.bind: episode.id}
        failures: Failures = {}
        for role, variable in (scope.episode_roles or {}).items():
            entity, problem = run.index.episode_role(episode, role)
            if entity is not None:
                values[variable] = entity
            else:
                amount = "no" if problem == "missing_binding" else "more than one"
                failures[variable] = (problem, f"episode {episode.id} has {amount} {role}")
        bounds = run.index.episode_bounds(episode)
        window = (episode.start_sec, bounds.latest_end)
        contexts.append(Context(episode, window, values, failures, run.index.members(episode)))
    return contexts


def triggers(run: RuleMatcher, context: Context) -> list[Trigger]:
    trigger = run.rule.trigger
    try:
        match trigger:
            case EventMatcher():
                return _event_triggers(run, trigger, context)
            case StateMatcher():
                return _state_triggers(run, trigger, context)
            case RelationMatcher():
                return _relation_triggers(run, trigger, context)
            case EpisodeMatcher():
                return _episode_triggers(run, trigger, context)
            case EpisodeEndMatcher():
                return _episode_end_triggers(run, trigger, context)
    except Undetermined:
        return []


def _event_triggers(run: RuleMatcher, matcher: EventMatcher, context: Context) -> list[Trigger]:
    found = []
    for event in context.pool:
        matched = run.match(matcher, event, context.values, context.failures)
        if matched is None:
            continue
        evidence = Evidence()
        evidence.add_event(event)
        found.append(Trigger(
            event.id, run.index.bounds(event), matched[0], matched[1], evidence,
            run.weakness(event), event=event,
        ))
    return found


def _state_triggers(run: RuleMatcher, matcher: StateMatcher, context: Context) -> list[Trigger]:
    found = []
    entities = run.resolve(matcher.entity, context.values, context.failures, context.episode)
    for entity in entities:
        for track in run.index.state_tracks(entity, matcher.property):
            pieces = state_profile(track, *context.window, matcher.value, matcher.knowledge)
            for span in matching_runs(pieces):
                evidence = Evidence()
                evidence.add_pieces(track, span)
                values = context.values | {TRIGGER_ENTITY: entity}
                if isinstance(matcher.entity, str):
                    values[matcher.entity] = entity
                found.append(Trigger(
                    track.id, Bounds.exact(span[0].start, span[-1].end), values,
                    dict(context.failures), evidence,
                ))
    return found


def _relation_triggers(run: RuleMatcher, matcher: RelationMatcher, context: Context) -> list[Trigger]:
    found = []
    subjects = run.maybe_resolve(matcher.subject, context.values, context.failures, context.episode)
    targets = run.maybe_resolve(matcher.target, context.values, context.failures, context.episode)
    tracks = [
        track for track in run.index.relation_tracks(matcher.relation)
        if subjects is None or track.subject_id in subjects
    ]
    for track in tracks:
        pieces = relation_profile(track, *context.window, None, matcher.knowledge)
        for target in sorted({p.target for p in pieces if p.status == "match" and p.target}):
            if targets is not None and target not in targets:
                continue
            own = relation_profile(track, *context.window, target, matcher.knowledge)
            for span in matching_runs(own):
                evidence = Evidence()
                evidence.add_pieces(track, span)
                values = context.values | {TRIGGER_ENTITY: track.subject_id}
                for selector, entity in ((matcher.subject, track.subject_id), (matcher.target, target)):
                    if isinstance(selector, str):
                        values[selector] = entity
                found.append(Trigger(
                    track.id, Bounds.exact(span[0].start, span[-1].end), values,
                    dict(context.failures), evidence,
                ))
    return found


def _episode_triggers(run: RuleMatcher, matcher: EpisodeMatcher, context: Context) -> list[Trigger]:
    if context.episode is not None and run.index.supports(
        "episode", context.episode.id, context.episode.kind, matcher.episode_kind,
    ):
        episodes = [context.episode]
    else:
        start, end = context.window
        episodes = [
            episode for episode in run.index.episodes_of(matcher.episode_kind)
            if episode.start_sec <= end and run.index.episode_bounds(episode).latest_end >= start
        ]
    found = []
    for episode in episodes:
        evidence = Evidence(episodes={episode.id}, observations=set(episode.basis_observation_ids))
        found.append(Trigger(
            episode.id, run.index.episode_bounds(episode), dict(context.values),
            dict(context.failures), evidence, episode=episode,
        ))
    return found


def _episode_end_triggers(run: RuleMatcher, matcher: EpisodeEndMatcher, context: Context) -> list[Trigger]:
    episodes = [context.episode] if context.episode else list(run.index.episodes.values())
    found = []
    for episode in sorted(episodes, key=lambda e: (e.start_sec, e.id)):
        if episode.end_boundary_status != matcher.requires_end_boundary or episode.end_sec is None:
            continue
        evidence = Evidence(episodes={episode.id}, observations=set(episode.basis_observation_ids))
        found.append(Trigger(
            episode.id, Bounds.exact(episode.end_sec, episode.end_sec), dict(context.values),
            dict(context.failures), evidence, episode=episode,
        ))
    return found

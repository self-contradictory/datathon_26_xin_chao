import logging
from dataclasses import dataclass, field
from time import perf_counter

from backend.followup.merge import merge_answer
from backend.followup.models import FollowupRecord, PlainTextModel
from backend.followup.planner import plan_questions
from backend.reconstruction.video import DecodedVideo
from backend.rules.engine import evaluate, select_rules
from backend.rules.findings import EvaluationReport, Mode
from backend.rules.models import RuleRegistry
from backend.steg import SparseTemporalEvidenceGraph

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RefinementResult:
    graph: SparseTemporalEvidenceGraph
    report: EvaluationReport
    calls: int
    checks: list[FollowupRecord] = field(default_factory=list)
    semantic_errors: list[str] = field(default_factory=list)
    frame_images: dict[float, bytes] = field(default_factory=dict)
    semantic_calls: int = 0
    plain_text_records: list[dict] = field(default_factory=list)


def refine(registry: RuleRegistry, graph: SparseTemporalEvidenceGraph, video: DecodedVideo,
           model: PlainTextModel, mode: Mode = "shadow", max_calls: int = 2,
           max_frames: int = 2, observer=None, semantic_matcher=None,
           verify_positive: bool = True, post_merge=None) -> RefinementResult:
    from backend.semantic.followup import TextObserver, TextSemanticMatcher, refresh_derived_states
    if max_calls < 0 or max_frames < 1:
        raise ValueError("Follow-up budget must be nonnegative and frame count positive")
    rules = select_rules(registry.rules, mode)
    semantics = semantic_matcher if semantic_matcher is not None else TextSemanticMatcher(model, rules)
    observer = observer if observer is not None else TextObserver(model, video, max_frames)
    post_merge = post_merge if post_merge is not None else refresh_derived_states
    result = RefinementResult(graph, evaluate(registry, graph, mode), 0)
    logger.info("Video %s: evaluating rules; follow-up budget=%s", video.path.stem, max_calls)
    seen = set()
    # Vocabulary alignment runs once and has its own counter. max_calls counts visual questions.
    candidates = semantics.candidates(result.graph) if max_calls else []
    if candidates:
        result.semantic_calls += 1
        started = perf_counter()
        logger.info("Video %s: text semantic alignment started", video.path.stem)
        try:
            result.graph = semantics.run(result.graph, candidates)
        except Exception as error:
            result.semantic_errors.append(str(error))
            logger.warning("Video %s: text semantic alignment failed: %s", video.path.stem, str(error).split("\n", 1)[0])
        logger.info("Video %s: text semantic alignment finished in %.1fs", video.path.stem, perf_counter() - started)
        result.report = evaluate(registry, result.graph, mode)
    while result.calls < max_calls:
        questions = [question for question in plan_questions(rules, result.graph, result.report, verify_positive)
                     if question.id not in seen and getattr(observer, "supports", lambda _: True)(question)]
        # Recheck current alerts before spending the visual budget on unrelated uncertain procedures.
        positive_rules = {f.rule_id for f in result.report.findings("VIOLATION")}
        questions.sort(key=lambda q: (q.rule_id not in positive_rules,
                                     q.matcher.kind not in {"state", "event", "relation"}))
        if not questions:
            break
        question = questions[0]
        seen.add(question.id)
        result.calls += 1
        record = FollowupRecord(question=question)
        started = perf_counter()
        logger.info("Video %s: visual follow-up %s/%s started", video.path.stem, result.calls, max_calls)
        try:
            record.answer, frames = observer.answer(question, result.graph)
            if record.answer.status != "not_visible":
                result.graph = merge_answer(result.graph, question, record.answer, frames)
                if post_merge is not None:
                    result.graph = post_merge(result.graph)
                for event in result.graph.events:
                    if (event.note or "").startswith("Plain-text follow-up") and event.inference_status == "directly_observed":
                        event.inference_status = "inferred_from_observations"
                result.frame_images.update({frame.evidence.timestamp_sec: frame.jpeg for frame in frames})
        except Exception as error:
            record.error = str(error)
            logger.warning("Video %s: visual follow-up failed: %s", video.path.stem, str(error).split("\n", 1)[0])
        logger.info("Video %s: visual follow-up finished in %.1fs", video.path.stem, perf_counter() - started)
        result.checks.append(record)
        result.report = evaluate(registry, result.graph, mode)
    result.plain_text_records = list(getattr(observer, "records", []))
    logger.info("Video %s: rule evaluation complete (%s visual checks, %s semantic pass)",
                video.path.stem, result.calls, result.semantic_calls)
    return result

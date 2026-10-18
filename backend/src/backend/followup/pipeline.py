import logging
from dataclasses import dataclass, field
from time import perf_counter

from backend.followup.merge import merge_answer
from backend.followup.models import FollowupRecord, StructuredModel
from backend.followup.observer import FocusedObserver
from backend.followup.planner import plan_questions
from backend.followup.semantic import SemanticMatcher
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


def refine(registry: RuleRegistry, graph: SparseTemporalEvidenceGraph, video: DecodedVideo,
           model: StructuredModel, mode: Mode = "shadow", max_calls: int = 8,
           max_frames: int = 8, observer=None, semantic_matcher=None,
           verify_positive: bool = False, post_merge=None) -> RefinementResult:
    rules = select_rules(registry.rules, mode)
    semantics = semantic_matcher if semantic_matcher is not None else SemanticMatcher(model, rules)
    observer = observer or FocusedObserver(model, video, max_frames)
    result = RefinementResult(graph, evaluate(registry, graph, mode), 0)
    logger.info("Video %s: evaluating rules; follow-up budget=%s", video.path.stem, max_calls)
    seen = set()
    while result.calls < max_calls:
        candidates = semantics.candidates(result.graph)
        if candidates:
            result.calls += 1
            started = perf_counter()
            logger.info("Video %s: semantic follow-up %s/%s started", video.path.stem, result.calls, max_calls)
            try:
                result.graph = semantics.run(result.graph, candidates)
            except ValueError as error:
                result.semantic_errors.append(str(error))
                logger.warning("Video %s: semantic follow-up failed: %s", video.path.stem, str(error).split("\n", 1)[0])
            logger.info("Video %s: semantic follow-up finished in %.1fs", video.path.stem, perf_counter() - started)
            result.report = evaluate(registry, result.graph, mode)
        questions = [question for question in plan_questions(rules, result.graph, result.report, verify_positive)
                     if question.id not in seen]
        if not questions:
            if candidates:
                continue
            break
        if result.calls == max_calls:
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
                result.frame_images.update({frame.evidence.timestamp_sec: frame.jpeg for frame in frames})
        except (ValueError, KeyError) as error:
            record.error = str(error)
            logger.warning("Video %s: visual follow-up failed: %s", video.path.stem, str(error).split("\n", 1)[0])
        logger.info("Video %s: visual follow-up finished in %.1fs", video.path.stem, perf_counter() - started)
        result.checks.append(record)
        result.report = evaluate(registry, result.graph, mode)
    logger.info("Video %s: rule evaluation complete (%s follow-up calls)", video.path.stem, result.calls)
    return result

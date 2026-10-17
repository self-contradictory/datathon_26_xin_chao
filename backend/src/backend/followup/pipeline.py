from dataclasses import dataclass, field

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
           max_frames: int = 8, observer=None) -> RefinementResult:
    rules = select_rules(registry.rules, mode)
    semantics = SemanticMatcher(model, rules)
    observer = observer or FocusedObserver(model, video, max_frames)
    result = RefinementResult(graph, evaluate(registry, graph, mode), 0)
    seen = set()
    while result.calls < max_calls:
        candidates = semantics.candidates(result.graph)
        if candidates:
            result.calls += 1
            try:
                result.graph = semantics.run(result.graph, candidates)
            except ValueError as error:
                result.semantic_errors.append(str(error))
            result.report = evaluate(registry, result.graph, mode)
        questions = [question for question in plan_questions(rules, result.graph, result.report)
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
        try:
            record.answer, frames = observer.answer(question, result.graph)
            if record.answer.status != "not_visible":
                result.graph = merge_answer(result.graph, question, record.answer, frames)
                result.frame_images.update({frame.evidence.timestamp_sec: frame.jpeg for frame in frames})
        except (ValueError, KeyError) as error:
            record.error = str(error)
        result.checks.append(record)
        result.report = evaluate(registry, result.graph, mode)
    return result

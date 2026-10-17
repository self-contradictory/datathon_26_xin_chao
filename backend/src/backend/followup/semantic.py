import json
import hashlib

from backend.followup.models import SemanticAnswer, StructuredModel
from backend.followup.vocabulary import vocabulary
from backend.rules.models import Rule
from backend.steg import SemanticSupport, SparseTemporalEvidenceGraph


class SemanticMatcher:
    def __init__(self, model: StructuredModel, rules: list[Rule]) -> None:
        self.model = model
        self.terms = vocabulary(rules)
        self.seen: set[str] = set()

    def candidates(self, graph: SparseTemporalEvidenceGraph, limit: int = 6) -> list[dict]:
        records = []
        for kind, collection, attribute in (
            ("action", graph.events, "action"), ("state", graph.state_tracks, "property"),
            ("relation", graph.relation_tracks, "relation"), ("entity", graph.entities, "subtype"),
            ("episode", graph.procedure_episodes, "kind"),
        ):
            for record in collection:
                observed = getattr(record, attribute)
                records.append((kind, record.id, observed, record.model_dump(mode="json")))
        for event in graph.events:
            for role in sorted({participant.role for participant in event.participants}):
                records.append(("role", event.id, role, event.model_dump(mode="json")))
        candidates = []
        for kind, identifier, observed, context in records:
            key = hashlib.sha256(json.dumps([kind, identifier, context], sort_keys=True).encode()).hexdigest()
            terms = self.terms.get(kind, [])
            if terms and observed not in terms and key not in self.seen:
                candidates.append({"key": key, "kind": kind, "record_id": identifier, "observed": observed,
                                   "requirements": terms, "context": context})
                if len(candidates) == limit:
                    break
        return candidates

    def run(self, graph: SparseTemporalEvidenceGraph, candidates: list[dict]) -> SparseTemporalEvidenceGraph:
        self.seen.update(item["key"] for item in candidates)
        records = [{"record_index": index, "kind": item["kind"], "observed": item["observed"],
                    "requirements": [{"requirement_index": position, "term": term}
                                     for position, term in enumerate(item["requirements"])],
                    "context": item["context"]} for index, item in enumerate(candidates)]
        prompt = (
            "Compare observed graph claims against rule vocabulary. Decide whether the observed claim "
            "supports each requirement in its actual context. This is directional entailment, not similarity. "
            "Writing alone does not establish signing; opening is not closing; giving is not receiving. "
            "Preserve the actor, object, direction and specificity. Return supports=true only when the claim "
            "establishes the requirement, false when it does not, null when the context is insufficient. "
            "Set equivalent=true only for interchangeable meanings. State and relation aliases must preserve "
            "all true/false values and targets; seated implies present, but not seated does not imply absent, "
            "so these properties are not equivalent. Never invert state values or relation direction. "
            "Do not invent video evidence or apply one record's match to other records. Return the supported "
            "and ambiguous candidates in matches; omit clearly unrelated requirements. Return at most two "
            "matches per observed record, preferring the most specific supported requirements. "
            "Keep each reason within twelve words. "
            "Copy the supplied zero-based record_index and requirement_index. The application keeps the "
            "original record IDs and terms; do not generate IDs or rewritten terms.\n"
            + json.dumps({"records": records,
                          "entities": [entity.model_dump(mode="json") for entity in graph.entities]}, ensure_ascii=False)
        )
        answer = self.model.structured(prompt, SemanticAnswer, max_new_tokens=2048)
        links = []
        for decision in answer.matches:
            if decision.record_index >= len(candidates):
                raise ValueError("Semantic answer references an unknown record index")
            item = candidates[decision.record_index]
            if decision.requirement_index >= len(item["requirements"]):
                raise ValueError("Semantic answer references an unknown requirement index")
            links.append(SemanticSupport(
                record_id=item["record_id"], kind=item["kind"], observed=item["observed"],
                requirement=item["requirements"][decision.requirement_index],
                supports=decision.supports, equivalent=decision.equivalent, reason=decision.reason,
            ))
        return graph.model_copy(update={"semantic_supports": graph.semantic_supports + links})

from base64 import b64encode
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from backend.rules.findings import EvaluationReport, Finding, UnknownKind
from backend.schemas import EvidenceFrame, Verdict, Violation


@dataclass(frozen=True, slots=True)
class ReportingPolicy:
    production_only: bool = True
    surface_unknown: frozenset[UnknownKind] = frozenset({"not_observed"})


DEFAULT_POLICY = ReportingPolicy()


def reportable(report: EvaluationReport, policy: ReportingPolicy = DEFAULT_POLICY) -> list[Finding]:
    found = []
    for finding in report.findings("VIOLATION", "UNKNOWN"):
        if policy.production_only and not finding.production:
            continue
        if finding.outcome == "UNKNOWN" and finding.unknown_kind not in policy.surface_unknown:
            continue
        found.append(finding)
    return found


def describe(finding: Finding) -> str:
    source = finding.source
    citation = f"{source.document}, {source.clause}" if source.clause else source.document
    lead = "Violation" if finding.outcome == "VIOLATION" else "Possible violation, not confirmed"
    approval = "" if finding.production else " The rule is still a candidate awaiting legal review."
    return f"{lead}: {finding.name}. Seen on video: {finding.reason}. Rule: {citation}.{approval}"


def to_violations(
    findings: Iterable[Finding], frame_jpeg: Callable[[float], bytes]
) -> list[Violation]:
    violations = []
    for finding in findings:
        times = [frame.timestamp_sec for frame in finding.evidence_frames] or [finding.timecode_sec]
        frames = [
            EvidenceFrame(timestamp_sec=time, image_base64=b64encode(frame_jpeg(time)).decode())
            for time in times[:3]
        ]
        violations.append(Violation(
            type=finding.name,
            timecode_sec=finding.timecode_sec,
            description=describe(finding),
            evidence_frames=frames,
        ))
    return violations


def verdict(violations: list[Violation]) -> Verdict:
    return "violation" if violations else "no_violation"

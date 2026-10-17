import {
  isDone,
  showsViolations,
  type EvidenceFrame,
  type Violation,
} from '@/api/types'
import { reviewSummary, type ReviewSummary } from '@/history/review'
import type { CheckRecord, ReviewDecision } from '@/history/types'
import { findRule, type Rule } from '@/rules'

export interface ActViolation {
  source: Violation
  position: number
  index: number
  timecode: number
  type: string
  rule: Rule | null
  frames: EvidenceFrame[]
  decision: ReviewDecision | null
}

export interface ActModel {
  number: string
  checkedAt: number
  fileName: string
  fileSize: number
  duration: number | null
  fileHash: string | null
  jobId: string
  violation: boolean
  review: ReviewSummary
  violations: ActViolation[]
}

export function buildReportModel(
  record: CheckRecord,
  duration: number | null,
): ActModel {
  const done = isDone(record.result) ? record.result : null
  const violation = done !== null && showsViolations(done)
  const ordered = (violation ? done.violations : [])
    .map((item, index) => ({ item, index }))
    .sort((a, b) => a.item.timecode_sec - b.item.timecode_sec)

  return {
    number: record.jobId.slice(0, 8),
    checkedAt: record.createdAt,
    fileName: record.fileName,
    fileSize: record.fileSize,
    duration,
    fileHash: record.fileHash,
    jobId: record.jobId,
    violation,
    review: reviewSummary(record.review, ordered.length),
    violations: ordered.map(({ item, index }) => ({
      source: item,
      position: index + 1,
      index,
      timecode: item.timecode_sec,
      type: item.type,
      rule: findRule(item.type),
      frames: item.evidence_frames.slice(0, 3),
      decision: record.review[index]?.decision ?? null,
    })),
  }
}

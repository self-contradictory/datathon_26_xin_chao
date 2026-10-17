import type { DoneJob } from '@/api/types'
import { withHumanReview } from '@/history/review'
import type { Review } from '@/history/types'

const SHORTEN_OVER = 60
const KEEP_CHARS = 40

function juryJob(job: DoneJob): DoneJob {
  return {
    job_id: job.job_id,
    status: job.status,
    verdict: job.verdict,
    violations: job.violations.map((violation) => ({
      type: violation.type,
      timecode_sec: violation.timecode_sec,
      description: violation.description,
      evidence_frames: violation.evidence_frames.map((frame) => ({
        timestamp_sec: frame.timestamp_sec,
        image_base64: frame.image_base64,
      })),
    })),
  }
}

export function fullJson(job: DoneJob, review: Review = {}): string {
  return JSON.stringify(withHumanReview(juryJob(job), review), null, 2)
}

export function screenJson(
  job: DoneJob,
  lengthLabel: (length: number) => string,
  review: Review = {},
): string {
  return JSON.stringify(
    withHumanReview(juryJob(job), review),
    (key, value: unknown) =>
      key === 'image_base64' &&
      typeof value === 'string' &&
      value.length > SHORTEN_OVER
        ? `${value.slice(0, KEEP_CHARS)}… (${lengthLabel(value.length)})`
        : value,
    2,
  )
}

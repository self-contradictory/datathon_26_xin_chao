import type { Review, ReviewDecision } from './types'

export interface ReviewSummary {
  total: number
  reviewed: number
  confirmed: number
  rejected: number
  complete: boolean
}

export interface HumanReview {
  reviewed_at: string
  items: { violation_index: number; decision: ReviewDecision }[]
}

function marks(review: Review, total: number) {
  return Object.entries(review)
    .map(([index, mark]) => ({ index: Number(index), mark }))
    .filter(({ index }) => index >= 0 && index < total)
    .sort((a, b) => a.index - b.index)
}

export function reviewSummary(review: Review, total: number): ReviewSummary {
  const list = marks(review, total)
  const confirmed = list.filter(({ mark }) => mark.decision === 'confirmed')
  return {
    total,
    reviewed: list.length,
    confirmed: confirmed.length,
    rejected: list.length - confirmed.length,
    complete: total > 0 && list.length === total,
  }
}

export function withHumanReview<T extends { violations: readonly unknown[] }>(
  job: T,
  review: Review,
): T & { human_review?: HumanReview } {
  const list = marks(review, job.violations.length)
  if (list.length === 0) return job
  const latest = Math.max(...list.map(({ mark }) => mark.at))
  return {
    ...job,
    human_review: {
      reviewed_at: new Date(latest).toISOString(),
      items: list.map(({ index, mark }) => ({
        violation_index: index,
        decision: mark.decision,
      })),
    },
  }
}

export function nextUnreviewed(
  review: Review,
  total: number,
  after: number,
): number | null {
  for (let step = 1; step <= total; step += 1) {
    const index = (after + step) % total
    if (!review[index]) return index
  }
  return null
}

import { describe, expect, test } from 'bun:test'
import { nextUnreviewed, reviewSummary, withHumanReview } from './review'
import type { Review } from './types'

const job = { job_id: 'j', violations: ['a', 'b', 'c'] }

describe('reviewSummary', () => {
  test('no marks', () => {
    expect(reviewSummary({}, 3)).toEqual({
      total: 3,
      reviewed: 0,
      confirmed: 0,
      rejected: 0,
      complete: false,
    })
  })

  test('partial and complete', () => {
    const partial: Review = { 2: { decision: 'rejected', at: 1 } }
    expect(reviewSummary(partial, 3)).toMatchObject({
      reviewed: 1,
      rejected: 1,
      complete: false,
    })
    const all: Review = {
      0: { decision: 'confirmed', at: 1 },
      1: { decision: 'confirmed', at: 2 },
      2: { decision: 'rejected', at: 3 },
    }
    expect(reviewSummary(all, 3)).toMatchObject({
      confirmed: 2,
      rejected: 1,
      complete: true,
    })
  })

  test('ignores marks for violations that do not exist', () => {
    expect(
      reviewSummary({ 7: { decision: 'confirmed', at: 1 } }, 3).reviewed,
    ).toBe(0)
  })
})

describe('withHumanReview', () => {
  test('no marks keeps the response untouched', () => {
    const result = withHumanReview(job, {})
    expect(result).toBe(job)
    expect('human_review' in result).toBe(false)
  })

  test('partial marks are listed by index with the latest time', () => {
    const result = withHumanReview(job, {
      2: { decision: 'rejected', at: Date.UTC(2026, 9, 17, 12, 0) },
      0: { decision: 'confirmed', at: Date.UTC(2026, 9, 17, 11, 0) },
    })
    expect(result.human_review).toEqual({
      reviewed_at: '2026-10-17T12:00:00.000Z',
      items: [
        { violation_index: 0, decision: 'confirmed' },
        { violation_index: 2, decision: 'rejected' },
      ],
    })
    expect(result.violations).toBe(job.violations)
  })

  test('all rejected stays a list of rejections', () => {
    const all: Review = {
      0: { decision: 'rejected', at: 1 },
      1: { decision: 'rejected', at: 1 },
      2: { decision: 'rejected', at: 1 },
    }
    const items = withHumanReview(job, all).human_review?.items ?? []
    expect(items.every((item) => item.decision === 'rejected')).toBe(true)
  })
})

describe('nextUnreviewed', () => {
  test('finds the next open violation and wraps around', () => {
    const review: Review = { 1: { decision: 'confirmed', at: 1 } }
    expect(nextUnreviewed(review, 3, 0)).toBe(2)
    expect(nextUnreviewed(review, 3, 2)).toBe(0)
  })

  test('returns null when everything is reviewed', () => {
    const review: Review = {
      0: { decision: 'confirmed', at: 1 },
      1: { decision: 'rejected', at: 1 },
    }
    expect(nextUnreviewed(review, 2, 0)).toBeNull()
  })
})

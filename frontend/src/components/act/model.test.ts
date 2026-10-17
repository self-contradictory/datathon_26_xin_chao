import { describe, expect, test } from 'bun:test'
import type { JobResponse, Violation } from '@/api/types'
import type { CheckRecord, Review } from '@/history/types'
import { RULES } from '@/rules'
import { buildReportModel } from './model'

function violation(type: string, timecode_sec: number): Violation {
  return {
    type,
    timecode_sec,
    description: `${type} at ${timecode_sec}`,
    evidence_frames: [1, 2, 3, 4].map((n) => ({
      timestamp_sec: timecode_sec + n / 10,
      image_base64: `f${n}`,
    })),
  }
}

function record(result: JobResponse, review: Review = {}): CheckRecord {
  return {
    jobId: 'abcdef1234567890',
    fileName: 'Х-17.mov',
    fileSize: 3032008,
    fileHash: 'ff',
    createdAt: 1000,
    result,
    review,
  }
}

const three: JobResponse = {
  job_id: 'abcdef1234567890',
  status: 'done',
  verdict: 'violation',
  violations: [
    violation(RULES[1]!.type, 40),
    violation('Тип, которого нет в словаре', 5),
    violation(RULES[0]!.type, 12),
  ],
}

describe('buildReportModel', () => {
  test('a clean video has no violation blocks', () => {
    const model = buildReportModel(
      record({
        job_id: 'abcdef1234567890',
        status: 'done',
        verdict: 'no_violation',
        violations: [],
      }),
      20,
    )
    expect(model).toMatchObject({
      number: 'abcdef12',
      violation: false,
      violations: [],
      duration: 20,
    })
    expect(model.review.total).toBe(0)
  })

  test('violations are ordered by time and keep their original index', () => {
    const model = buildReportModel(record(three), null)
    expect(
      model.violations.map((v) => [v.position, v.index, v.timecode]),
    ).toEqual([
      [1, 1, 5],
      [2, 2, 12],
      [3, 0, 40],
    ])
    expect(model.violations[0]!.rule).toBeNull()
    expect(model.violations[0]!.type).toBe('Тип, которого нет в словаре')
    expect(model.violations[1]!.rule?.id).toBe(RULES[0]!.id)
    expect(model.violations.every((v) => v.frames.length === 3)).toBe(true)
  })

  test('partial marks show per violation and in the summary', () => {
    const model = buildReportModel(
      record(three, {
        0: { decision: 'confirmed', at: 1 },
        2: { decision: 'rejected', at: 2 },
      }),
      null,
    )
    expect(model.violations.map((v) => v.decision)).toEqual([
      null,
      'rejected',
      'confirmed',
    ])
    expect(model.review).toMatchObject({
      confirmed: 1,
      rejected: 1,
      complete: false,
    })
  })
})

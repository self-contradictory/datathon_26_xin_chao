import { describe, expect, test } from 'bun:test'
import { ApiParseError, parseAnalyzeResponse, parseJobResponse } from './parse'
import { JobError } from './source'

const CASE_EXAMPLE = {
  job_id: '3f2a9c1e',
  status: 'done',
  verdict: 'violation',
  violations: [
    {
      type: 'Название типа нарушения',
      timecode_sec: 44.2,
      description: 'Что видно на видео и почему это нарушение',
      evidence_frames: [{ timestamp_sec: 44.2, image_base64: '/9j/4AAQ...' }],
    },
  ],
}

const frame = { timestamp_sec: 1, image_base64: 'AAAA' }
const violation = {
  type: 'T',
  timecode_sec: 1,
  description: 'D',
  evidence_frames: [frame],
}

function problemAt(value: unknown): string {
  try {
    parseJobResponse(value)
  } catch (error) {
    if (error instanceof ApiParseError) return error.path
    throw error
  }
  throw new Error('expected ApiParseError')
}

describe('parseJobResponse', () => {
  test('accepts the case example as is', () => {
    expect(parseJobResponse(CASE_EXAMPLE)).toEqual(CASE_EXAMPLE as never)
  })

  test('accepts a clean result with an empty list', () => {
    const job = parseJobResponse({
      job_id: 'a',
      status: 'done',
      verdict: 'no_violation',
      violations: [],
    })
    expect(job.violations).toEqual([])
  })

  test('accepts processing with missing or null verdict (schemas.py defaults)', () => {
    expect(parseJobResponse({ job_id: 'a', status: 'processing' })).toEqual({
      job_id: 'a',
      status: 'processing',
      verdict: null,
      violations: null,
    })
    expect(
      parseJobResponse({
        job_id: 'a',
        status: 'failed',
        verdict: null,
        violations: null,
      }).status,
    ).toBe('failed')
  })

  test('rejects unknown status and verdict values', () => {
    expect(problemAt({ job_id: 'a', status: 'queued' })).toBe('job.status')
    expect(
      problemAt({
        job_id: 'a',
        status: 'done',
        verdict: 'maybe',
        violations: [],
      }),
    ).toBe('job.verdict')
  })

  test('done needs a verdict and a list', () => {
    expect(problemAt({ job_id: 'a', status: 'done', violations: [] })).toBe(
      'job.verdict',
    )
    expect(
      problemAt({ job_id: 'a', status: 'done', verdict: 'violation' }),
    ).toBe('job.violations')
  })

  test('evidence_frames must hold 1 to 3 frames (schemas.py min/max)', () => {
    const job = (frames: unknown[]) => ({
      job_id: 'a',
      status: 'done',
      verdict: 'violation',
      violations: [{ ...violation, evidence_frames: frames }],
    })
    expect(problemAt(job([]))).toBe('job.violations[0].evidence_frames')
    expect(problemAt(job([frame, frame, frame, frame]))).toBe(
      'job.violations[0].evidence_frames',
    )
    expect(
      parseJobResponse(job([frame, frame, frame])).violations?.[0]
        ?.evidence_frames,
    ).toHaveLength(3)
  })

  test('the old design field names are rejected', () => {
    const job = {
      job_id: 'a',
      status: 'done',
      verdict: 'violation',
      violations: [
        {
          ...violation,
          evidence_frames: [{ timecode_sec: 1, image: 'frames/1.jpg' }],
        },
      ],
    }
    expect(problemAt(job)).toBe(
      'job.violations[0].evidence_frames[0].timestamp_sec',
    )
  })

  test('is exactly as strict as schemas.py: str and float', () => {
    const job = (v: object) => ({
      job_id: 'a',
      status: 'done',
      verdict: 'violation',
      violations: [{ ...violation, ...v }],
    })
    expect(problemAt(job({ timecode_sec: '7' }))).toBe(
      'job.violations[0].timecode_sec',
    )
    expect(problemAt(job({ type: 7 }))).toBe('job.violations[0].type')
    expect(() =>
      parseJobResponse(job({ type: '', description: '' })),
    ).not.toThrow()
    expect(() => parseJobResponse(job({ timecode_sec: -1 }))).not.toThrow()
  })

  test('a parse error is a bad_response JobError', () => {
    try {
      parseJobResponse({ job_id: 'a', status: 'queued' })
    } catch (error) {
      expect(error).toBeInstanceOf(JobError)
      expect((error as JobError).kind).toBe('bad_response')
    }
  })

  test('rejects non-objects', () => {
    expect(problemAt(null)).toBe('job')
    expect(problemAt([])).toBe('job')
  })
})

describe('parseAnalyzeResponse', () => {
  test('takes job_id only (lead: POST /analyze returns job_id)', () => {
    expect(parseAnalyzeResponse({ job_id: 'abc' })).toEqual({ job_id: 'abc' })
    expect(
      parseAnalyzeResponse({ job_id: 'abc', status: 'processing' }),
    ).toEqual({ job_id: 'abc' })
  })

  test('rejects a missing job_id', () => {
    expect(() => parseAnalyzeResponse({})).toThrow(ApiParseError)
  })
})

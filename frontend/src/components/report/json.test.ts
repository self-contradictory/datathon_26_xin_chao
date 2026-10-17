import { describe, expect, test } from 'bun:test'
import type { DoneJob } from '@/api/types'
import { fullJson, screenJson } from './json'

const LONG = 'A'.repeat(45213)
const SHORT = 'B'.repeat(60)

const JOB: DoneJob = {
  job_id: 'job-1',
  status: 'done',
  verdict: 'violation',
  violations: [
    {
      type: 'Касса без присмотра',
      timecode_sec: 7,
      description: 'Ящик открыт, кассира нет в кадре.',
      evidence_frames: [
        { timestamp_sec: 6.8, image_base64: LONG },
        { timestamp_sec: 7.4, image_base64: SHORT },
      ],
    },
  ],
}

describe('report json', () => {
  test('fullJson keeps the jury shape, key order and full images', () => {
    const extra = { ...JOB, note: 'ui only' } as DoneJob
    const text = fullJson(extra)
    expect(JSON.parse(text)).toEqual(JOB)
    expect(Object.keys(JSON.parse(text))).toEqual([
      'job_id',
      'status',
      'verdict',
      'violations',
    ])
    expect(text).toContain(LONG)
    expect(text).toStartWith('{\n  "job_id": "job-1",')
  })

  test('screenJson shortens only images longer than 60 characters', () => {
    const text = screenJson(JOB, (n) => `${n} символов`)
    const shown = JSON.parse(text) as DoneJob
    const [first, second] = shown.violations[0]!.evidence_frames
    expect(first!.image_base64).toBe(`${'A'.repeat(40)}… (45213 символов)`)
    expect(second!.image_base64).toBe(SHORT)
    expect(shown.violations[0]!.description).toBe(
      JOB.violations[0]!.description,
    )
  })

  test('a clean job has an empty violations list', () => {
    const clean: DoneJob = { ...JOB, verdict: 'no_violation', violations: [] }
    expect(JSON.parse(screenJson(clean, String))).toEqual(clean)
  })
})

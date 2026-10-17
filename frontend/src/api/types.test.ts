import { describe, expect, test } from 'bun:test'
import { showsViolations, type DoneJob, type Violation } from './types'

const violation: Violation = {
  type: 'Наличные вне зоны видимости камеры',
  timecode_sec: 7,
  description: 'Кассир убрал деньги под стол.',
  evidence_frames: [{ timestamp_sec: 7, image_base64: 'AAAA' }],
}

function job(verdict: DoneJob['verdict'], violations: Violation[]): DoneJob {
  return { job_id: 'j', status: 'done', verdict, violations }
}

describe('showsViolations', () => {
  test('a violation verdict with violations shows them', () => {
    expect(showsViolations(job('violation', [violation]))).toBe(true)
  })

  test('a violation verdict without any violation reads as clean', () => {
    expect(showsViolations(job('violation', []))).toBe(false)
  })

  test('a clean verdict never shows violations', () => {
    expect(showsViolations(job('no_violation', [violation]))).toBe(false)
  })
})

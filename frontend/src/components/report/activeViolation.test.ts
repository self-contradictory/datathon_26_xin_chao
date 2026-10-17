import { describe, expect, test } from 'bun:test'
import { activeViolationIndex, stepIndex } from './activeViolation'

const at = (...times: number[]) =>
  times.map((timecode_sec) => ({ timecode_sec }))

describe('activeViolationIndex', () => {
  test('no violation near the playhead', () => {
    expect(activeViolationIndex(at(10, 40), 25)).toBeNull()
    expect(activeViolationIndex([], 5)).toBeNull()
  })

  test('the ±3 s edge counts as active', () => {
    expect(activeViolationIndex(at(10), 7)).toBe(0)
    expect(activeViolationIndex(at(10), 13)).toBe(0)
    expect(activeViolationIndex(at(10), 13.01)).toBeNull()
  })

  test('overlapping windows pick the closest violation', () => {
    expect(activeViolationIndex(at(10, 14), 11)).toBe(0)
    expect(activeViolationIndex(at(10, 14), 13)).toBe(1)
    expect(activeViolationIndex(at(14, 10), 12)).toBe(0)
  })
})

describe('stepIndex', () => {
  test('wraps around both ways', () => {
    expect(stepIndex(2, 1, 3)).toBe(0)
    expect(stepIndex(0, -1, 3)).toBe(2)
  })
})

import { describe, expect, test } from 'bun:test'
import { stepStates, uploadPercent } from './steps'

describe('processing steps', () => {
  test('uploading: upload is active, analysis waits', () => {
    expect(stepStates('uploading', null)).toEqual({
      upload: 'active',
      analysis: 'pending',
    })
  })

  test('analyzing: upload is done, analysis is active', () => {
    expect(stepStates('analyzing', null)).toEqual({
      upload: 'done',
      analysis: 'active',
    })
  })

  test('failed during upload', () => {
    expect(stepStates('failed', 'upload')).toEqual({
      upload: 'error',
      analysis: 'pending',
    })
  })

  test('failed during analysis', () => {
    expect(stepStates('failed', 'analysis')).toEqual({
      upload: 'done',
      analysis: 'error',
    })
  })

  test('an unknown failed step defaults to the analysis', () => {
    expect(stepStates('failed', null)).toEqual({
      upload: 'done',
      analysis: 'error',
    })
  })

  test('uploadPercent', () => {
    expect(uploadPercent(0)).toBe(0)
    expect(uploadPercent(0.4)).toBe(40)
    expect(uploadPercent(0.999)).toBe(99)
    expect(uploadPercent(1)).toBe(100)
    expect(uploadPercent(1.2)).toBe(100)
    expect(uploadPercent(-1)).toBe(0)
    expect(uploadPercent(Number.NaN)).toBe(0)
  })
})

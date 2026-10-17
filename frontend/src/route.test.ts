import { describe, expect, test } from 'bun:test'
import { parseHash } from './route'

describe('parseHash', () => {
  test('reads rule and check ids', () => {
    expect(parseHash('#/rules/cashOutOfView')).toEqual({
      page: 'rules',
      ruleId: 'cashOutOfView',
    })
    expect(parseHash('#/check/fx-1')).toEqual({ page: 'check', jobId: 'fx-1' })
  })

  test('survives a malformed percent escape', () => {
    expect(parseHash('#/check/50%')).toEqual({ page: 'history' })
    expect(parseHash('#/rules/%E0')).toEqual({ page: 'rules' })
  })
})

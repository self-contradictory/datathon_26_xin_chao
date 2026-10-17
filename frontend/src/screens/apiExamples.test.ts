import { describe, expect, test } from 'bun:test'
import { parseAnalyzeResponse, parseJobResponse } from '@/api/parse'
import { isDone } from '@/api/types'
import { findRule } from '@/rules'
import {
  ANALYZE_RESPONSE,
  analyzeCurl,
  apiBase,
  EXAMPLE_JOB_ID,
  JOB_RESPONSE,
  jobCurl,
  toJson,
} from './apiExamples'

describe('API page examples', () => {
  test('POST /analyze response passes parseAnalyzeResponse', () => {
    const shown = JSON.parse(toJson(ANALYZE_RESPONSE))
    expect(parseAnalyzeResponse(shown)).toEqual(shown)
  })

  test('POST /analyze response has only job_id', () => {
    expect(Object.keys(ANALYZE_RESPONSE)).toEqual(['job_id'])
  })

  test('GET /jobs response passes parseJobResponse as a finished job', () => {
    const shown = JSON.parse(toJson(JOB_RESPONSE))
    const job = parseJobResponse(shown)
    expect(job).toEqual(shown)
    expect(isDone(job)).toBe(true)
    expect(job.verdict).toBe('violation')
    expect(job.violations).toHaveLength(1)
  })

  test('violation type in the example is one of the listed rules', () => {
    for (const violation of JOB_RESPONSE.violations) {
      expect(findRule(violation.type)).not.toBeNull()
    }
  })

  test('both requests use the same job and the X-API-Key header', () => {
    expect(ANALYZE_RESPONSE.job_id).toBe(EXAMPLE_JOB_ID)
    expect(JOB_RESPONSE.job_id).toBe(EXAMPLE_JOB_ID)
    const host = 'https://api.example.kz'
    expect(analyzeCurl(host)).toContain(`"${apiBase(host)}/analyze"`)
    expect(jobCurl(host)).toContain(`"${apiBase(host)}/jobs/${EXAMPLE_JOB_ID}"`)
    for (const curl of [analyzeCurl(host), jobCurl(host)]) {
      expect(curl).toContain('-H "X-API-Key: $FORTE_API_KEY"')
    }
    expect(analyzeCurl(host)).toMatch(/-F "file=@[^"]+\.mov"/)
  })
})

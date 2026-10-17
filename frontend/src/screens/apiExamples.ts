import { ANALYZE_PATH, API_PREFIX, apiUrl, jobPath } from '@/api/paths'
import type { AnalyzeResponse, DoneJob } from '@/api/types'

export const EXAMPLE_JOB_ID = '3f2a9c1e'

const FRAME_BASE64 = '/9j/4AAQ...'

export const ANALYZE_RESPONSE: AnalyzeResponse = { job_id: EXAMPLE_JOB_ID }

export const JOB_RESPONSE: DoneJob = {
  job_id: EXAMPLE_JOB_ID,
  status: 'done',
  verdict: 'violation',
  violations: [
    {
      type: 'Наличные вне зоны видимости камеры',
      timecode_sec: 7,
      description:
        'Кассир опускает руки с купюрами ниже края стола, 2 с их не видно.',
      evidence_frames: [
        { timestamp_sec: 6.8, image_base64: FRAME_BASE64 },
        { timestamp_sec: 7.4, image_base64: FRAME_BASE64 },
        { timestamp_sec: 8.1, image_base64: FRAME_BASE64 },
      ],
    },
  ],
}

export function apiBase(origin: string): string {
  return apiUrl(origin, API_PREFIX)
}

export function authHeader(key: string): string {
  return `X-API-Key: ${key}`
}

export function analyzeCurl(origin: string): string {
  return [
    `curl -X POST "${apiUrl(origin, ANALYZE_PATH)}" \\`,
    '  -H "X-API-Key: $FORTE_API_KEY" \\',
    '  -F "file=@Х-17.mov"',
  ].join('\n')
}

export function jobCurl(origin: string): string {
  return [
    `curl "${apiUrl(origin, jobPath(EXAMPLE_JOB_ID))}" \\`,
    '  -H "X-API-Key: $FORTE_API_KEY"',
  ].join('\n')
}

export function toJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

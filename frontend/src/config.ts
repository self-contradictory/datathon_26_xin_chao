import { createFixtureSource } from '@/api/fixtureSource'
import { createHttpSource } from '@/api/httpSource'
import type { JobSource } from '@/api/source'
import { captureFrames } from '@/utils/frames'

function publicEnv(read: () => string | undefined): string {
  try {
    return read() ?? ''
  } catch {
    return ''
  }
}

export const API_BASE_URL = publicEnv(() => process.env.BUN_PUBLIC_API_URL)
const API_KEY = publicEnv(() => process.env.BUN_PUBLIC_API_KEY)
function demoRequested(): boolean {
  if (process.env.NODE_ENV === 'production') return false
  if (typeof location === 'undefined') return false
  return new URLSearchParams(location.search).has('demo')
}

export const USE_FIXTURES =
  publicEnv(() => process.env.BUN_PUBLIC_DATA_SOURCE) === 'fixtures' ||
  demoRequested()

function fixtureSource(): JobSource {
  return createFixtureSource({
    capture: async (file, times) => {
      const url = URL.createObjectURL(file)
      try {
        return await captureFrames(url, times)
      } finally {
        URL.revokeObjectURL(url)
      }
    },
  })
}

export const jobSource: JobSource = USE_FIXTURES
  ? fixtureSource()
  : createHttpSource({ baseUrl: API_BASE_URL, apiKey: API_KEY })

export const POLL_INTERVAL_MS = USE_FIXTURES ? 1000 : 2000
export const POLL_TIMEOUT_MS = 5 * 60 * 1000
export const MAX_BATCH_FILES = 10

import { createFixtureSource } from '@/api/fixtureSource'
import type { JobSource } from '@/api/source'
import { captureFrames } from '@/utils/frames'

export const jobSource: JobSource = createFixtureSource({
  capture: async (file, times) => {
    const url = URL.createObjectURL(file)
    try {
      return await captureFrames(url, times)
    } finally {
      URL.revokeObjectURL(url)
    }
  },
})

export const POLL_INTERVAL_MS = 1000
export const POLL_TIMEOUT_MS = 5 * 60 * 1000

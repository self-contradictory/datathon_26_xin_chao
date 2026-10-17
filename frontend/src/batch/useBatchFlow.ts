import { useEffect, useState, useSyncExternalStore } from 'react'
import type { PollingOptions } from '@/api/check'
import type { JobSource } from '@/api/source'
import { pickVideo, revokeVideo, withPoster } from '@/video'
import { createBatchRunner } from './runner'

export function useBatchFlow(
  source: JobSource,
  { intervalMs, timeoutMs }: PollingOptions,
) {
  const [runner] = useState(() =>
    createBatchRunner({
      source,
      intervalMs,
      timeoutMs,
      pickVideo,
      withPoster,
      revokeVideo,
    }),
  )
  const state = useSyncExternalStore(runner.subscribe, runner.getState)

  useEffect(() => () => runner.reset(), [runner])

  return {
    state,
    start: runner.start,
    retry: runner.retry,
    open: runner.open,
    close: runner.close,
    reset: runner.reset,
  }
}

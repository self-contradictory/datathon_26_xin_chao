import { useEffect, useState, useSyncExternalStore } from 'react'
import type { PollingOptions } from '@/api/check'
import type { JobSource } from '@/api/source'
import { isDone } from '@/api/types'
import { findSaved, saveCheck } from '@/history/save'
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
      findSaved: async (file) => {
        const saved = await findSaved(file)
        return saved && isDone(saved.result)
          ? { job: saved.result, checkedAt: saved.createdAt }
          : null
      },
      onDone: (item, job, checkedAt) =>
        void saveCheck({
          job,
          file: item.video.file,
          checkedAt,
          poster: item.video.posterUrl,
          duration: item.video.duration,
        }).catch(() => {}),
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

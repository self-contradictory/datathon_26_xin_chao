import { CheckFailure, uploadVideo, waitForJob } from '@/api/check'
import type { JobSource } from '@/api/source'
import type { DoneJob } from '@/api/types'
import { uploadPercent } from '@/components/processing/steps'
import type { RejectedFile } from '@/utils/file'
import type { PickedVideo } from '@/video'
import { batchReducer, EMPTY_BATCH, nextQueued, pausesQueue } from './batch'
import type { BatchAction, BatchItem, BatchState } from './types'

export interface BatchRunnerOptions {
  source: JobSource
  intervalMs: number
  timeoutMs: number
  pickVideo: (file: File) => PickedVideo
  withPoster: (video: PickedVideo) => Promise<PickedVideo>
  revokeVideo: (video: PickedVideo) => void
  now?: () => number
}

export interface BatchRunner {
  getState: () => BatchState
  subscribe: (listener: () => void) => () => void
  start: (files: readonly File[], rejected: readonly RejectedFile[]) => void
  retry: (id: string) => void
  open: (id: string) => void
  close: () => void
  reset: () => void
}

type Outcome = 'next' | 'pause'

function isGone(error: unknown): boolean {
  return (
    error instanceof CheckFailure &&
    (error.kind === 'failed' || error.kind === 'not_found')
  )
}

export function createBatchRunner({
  source,
  intervalMs,
  timeoutMs,
  pickVideo,
  withPoster,
  revokeVideo,
  now = () => Date.now(),
}: BatchRunnerOptions): BatchRunner {
  let state = EMPTY_BATCH
  const listeners = new Set<() => void>()
  let batch = 0
  let loopBatch: number | null = null
  let controller = new AbortController()
  let lastId = 0

  function dispatch(action: BatchAction) {
    const next = batchReducer(state, action)
    if (next === state) return
    state = next
    for (const listener of listeners) listener()
  }

  async function checkItem(
    item: BatchItem,
    token: number,
    signal: AbortSignal,
  ): Promise<Outcome> {
    const live = () => token === batch
    const update = (action: BatchAction) => {
      if (live()) dispatch(action)
    }
    const { id } = item
    const wait = { intervalMs, timeoutMs, signal }
    let jobId = item.stage.kind === 'queued' ? item.stage.jobId : null

    try {
      let job: DoneJob | null = null
      if (jobId) {
        update({ type: 'analyzing', id, jobId })
        try {
          job = await waitForJob(source, jobId, wait)
        } catch (error) {
          if (!isGone(error)) throw error
          jobId = null
        }
      }
      if (!job) {
        if (!live()) return 'next'
        let percent = 0
        update({ type: 'uploading', id, progress: 0 })
        jobId = await uploadVideo(source, item.video.file, {
          signal,
          onUploadProgress: (progress) => {
            if (uploadPercent(progress) === percent) return
            percent = uploadPercent(progress)
            update({ type: 'uploading', id, progress })
          },
        })
        update({ type: 'analyzing', id, jobId })
        job = await waitForJob(source, jobId, wait)
      }
      update({ type: 'done', id, job, checkedAt: now() })
      return 'next'
    } catch (error) {
      const failure =
        error instanceof CheckFailure
          ? error
          : new CheckFailure('failed', 'analysis')
      update({
        type: 'failed',
        id,
        error: failure.kind,
        step: failure.step,
        jobId: failure.step === 'analysis' ? jobId : null,
      })
      return pausesQueue(failure.kind) ? 'pause' : 'next'
    }
  }

  async function runQueue(token: number, signal: AbortSignal) {
    loopBatch = token
    try {
      for (;;) {
        if (token !== batch) return
        const item = nextQueued(state.items)
        if (!item) return
        const outcome = await checkItem(item, token, signal)
        if (outcome === 'pause') return
      }
    } finally {
      if (loopBatch === token) loopBatch = null
    }
  }

  async function loadPosters(token: number, items: readonly BatchItem[]) {
    for (const item of items) {
      if (token !== batch) return
      const video = await withPoster(item.video).catch(() => null)
      if (video && token === batch) {
        dispatch({ type: 'poster', id: item.id, video })
      }
    }
  }

  function reset() {
    batch += 1
    controller.abort()
    controller = new AbortController()
    for (const item of state.items) revokeVideo(item.video)
    dispatch({ type: 'reset' })
  }

  function start(files: readonly File[], rejected: readonly RejectedFile[]) {
    reset()
    const token = batch
    const items: BatchItem[] = files.map((file) => {
      lastId += 1
      return {
        id: `video-${lastId}`,
        video: pickVideo(file),
        stage: { kind: 'queued', jobId: null },
      }
    })
    dispatch({ type: 'start', items, rejected: [...rejected] })
    void loadPosters(token, items)
    void runQueue(token, controller.signal)
  }

  function retry(id: string) {
    const before = state
    dispatch({ type: 'retry', id })
    if (state === before || loopBatch === batch) return
    void runQueue(batch, controller.signal)
  }

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    start,
    retry,
    open: (id) => dispatch({ type: 'open', id }),
    close: () => dispatch({ type: 'close' }),
    reset,
  }
}

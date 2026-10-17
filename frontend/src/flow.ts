import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckFailure, runCheck } from '@/api/check'
import type { JobErrorKind, JobSource } from '@/api/source'
import type { DoneJob } from '@/api/types'
import type { ProcessingPhase, ProcessingStep } from '@/screens/contracts'
import { pickVideo, revokeVideo, withPoster, type PickedVideo } from '@/video'

interface ProcessingState {
  screen: 'processing'
  video: PickedVideo
  phase: ProcessingPhase
  uploadProgress: number
  startedAt: number
  stoppedAt: number | null
  error: JobErrorKind | null
  failedStep: ProcessingStep | null
}

export type FlowState =
  | { screen: 'upload' }
  | ProcessingState
  | { screen: 'report'; video: PickedVideo; job: DoneJob; checkedAt: number }

export function useJobFlow(
  source: JobSource,
  { intervalMs, timeoutMs }: { intervalMs: number; timeoutMs: number },
) {
  const [state, setState] = useState<FlowState>({ screen: 'upload' })
  const run = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const videoRef = useRef<PickedVideo | null>(null)

  const cancelRun = useCallback(() => {
    run.current += 1
    controller.current?.abort()
    controller.current = null
  }, [])

  const releaseVideo = useCallback(() => {
    if (videoRef.current) revokeVideo(videoRef.current)
    videoRef.current = null
  }, [])

  useEffect(
    () => () => {
      cancelRun()
      releaseVideo()
    },
    [cancelRun, releaseVideo],
  )

  const process = useCallback(
    async (video: PickedVideo) => {
      cancelRun()
      const token = run.current
      const live = () => token === run.current
      const abort = new AbortController()
      controller.current = abort
      const startedAt = Date.now()
      setState({
        screen: 'processing',
        video,
        phase: 'uploading',
        uploadProgress: 0,
        startedAt,
        stoppedAt: null,
        error: null,
        failedStep: null,
      })
      const update = (change: Partial<ProcessingState>) => {
        if (!live()) return
        setState((prev) =>
          prev.screen === 'processing' ? { ...prev, ...change } : prev,
        )
      }

      try {
        const job = await runCheck(source, video.file, {
          intervalMs,
          timeoutMs,
          signal: abort.signal,
          onUploadProgress: (uploadProgress) => update({ uploadProgress }),
          onUploaded: () => update({ phase: 'analyzing', uploadProgress: 1 }),
        })
        if (!live()) return
        setState({
          screen: 'report',
          video: videoRef.current ?? video,
          job,
          checkedAt: Date.now(),
        })
      } catch (error) {
        const failure =
          error instanceof CheckFailure
            ? error
            : new CheckFailure('failed', 'analysis')
        update({
          phase: 'failed',
          stoppedAt: Date.now(),
          error: failure.kind,
          failedStep: failure.step,
        })
      }
    },
    [source, intervalMs, timeoutMs, cancelRun],
  )

  const start = useCallback(
    (file: File) => {
      releaseVideo()
      const video = pickVideo(file)
      videoRef.current = video
      void withPoster(video)
        .then((updated) => {
          if (videoRef.current !== video) return
          videoRef.current = updated
          setState((prev) =>
            prev.screen === 'upload' ? prev : { ...prev, video: updated },
          )
        })
        .catch(() => {})
      void process(video)
    },
    [process, releaseVideo],
  )

  const retry = useCallback(() => {
    if (videoRef.current) void process(videoRef.current)
  }, [process])

  const reset = useCallback(() => {
    cancelRun()
    releaseVideo()
    setState({ screen: 'upload' })
  }, [cancelRun, releaseVideo])

  return { state, start, retry, reset }
}

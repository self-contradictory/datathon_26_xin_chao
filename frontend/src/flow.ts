import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckFailure, runCheck } from '@/api/check'
import type { JobErrorKind, JobSource } from '@/api/source'
import type { DoneJob } from '@/api/types'
import type { ProcessingPhase, ProcessingStep } from '@/screens/contracts'
import { captureFrames, jpegDataUrl } from '@/utils/frames'

export interface PickedVideo {
  file: File
  url: string
  posterUrl: string | null
  duration: number | null
}

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
  const videoRef = useRef<PickedVideo | null>(null)

  const releaseVideo = useCallback(() => {
    if (videoRef.current) URL.revokeObjectURL(videoRef.current.url)
    videoRef.current = null
  }, [])

  useEffect(() => releaseVideo, [releaseVideo])

  const process = useCallback(
    async (video: PickedVideo) => {
      const token = ++run.current
      const live = () => token === run.current
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
    [source, intervalMs, timeoutMs],
  )

  const start = useCallback(
    (file: File) => {
      releaseVideo()
      const video: PickedVideo = {
        file,
        url: URL.createObjectURL(file),
        posterUrl: null,
        duration: null,
      }
      videoRef.current = video
      void captureFrames(video.url, [0])
        .then(({ duration, frames }) => {
          if (videoRef.current !== video) return
          const updated: PickedVideo = {
            ...video,
            duration: duration || null,
            posterUrl: frames[0] ? jpegDataUrl(frames[0].base64) : null,
          }
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
    run.current += 1
    releaseVideo()
    setState({ screen: 'upload' })
  }, [releaseVideo])

  return { state, start, retry, reset }
}

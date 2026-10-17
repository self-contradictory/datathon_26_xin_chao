import { useEffect, useRef } from 'react'
import { FileMeta } from '@/components/FileMeta'
import { useStrings } from '@/i18n'
import { ElapsedTimer } from '@/components/processing/ElapsedTimer'
import { ErrorPanel } from '@/components/processing/ErrorPanel'
import { LiveStatus } from '@/components/processing/LiveStatus'
import { StepList } from '@/components/processing/StepList'
import { stepStates } from '@/components/processing/steps'
import { VideoPreview } from '@/components/processing/VideoPreview'
import type { ProcessingScreenProps } from './contracts'

export function ProcessingScreen({
  fileName,
  fileSize,
  duration,
  posterUrl,
  phase,
  uploadProgress,
  startedAt,
  stoppedAt,
  error,
  failedStep,
  onRetry,
  onNewVideo,
}: ProcessingScreenProps) {
  const t = useStrings('processing')
  const failed = phase === 'failed'
  const announcement =
    phase === 'uploading'
      ? t.nowUploading
      : phase === 'analyzing'
        ? t.nowAnalyzing
        : ''

  const titleRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    if (phase === 'uploading') titleRef.current?.focus()
  }, [phase])

  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-8 px-4 pt-8 pb-12 sm:px-6 lg:pt-12 lg:pb-16">
      <div className="flex max-w-[72ch] flex-col gap-1">
        <h1
          ref={titleRef}
          tabIndex={-1}
          className="text-title font-semibold focus:outline-none"
        >
          {t.title}
        </h1>
        <p className="text-text-muted">
          {failed ? t.subtitleFailed : t.subtitle}
        </p>
      </div>
      <LiveStatus message={announcement} />

      <div className="grid max-w-[560px] grid-cols-[auto_minmax(0,1fr)] items-start gap-x-4 gap-y-6 lg:max-w-none lg:grid-cols-[auto_minmax(0,560px)] lg:grid-rows-[auto_1fr] lg:justify-start lg:gap-x-12">
        <VideoPreview
          fileName={fileName}
          posterUrl={posterUrl}
          duration={duration}
          className="lg:row-span-2"
        />

        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="text-section font-semibold wrap-anywhere">
            {fileName}
          </h2>
          <FileMeta size={fileSize} duration={duration} />
        </div>

        <div className="col-span-2 flex min-w-0 flex-col gap-6 lg:col-span-1 lg:col-start-2">
          <StepList
            states={stepStates(phase, failedStep)}
            uploadProgress={uploadProgress}
          />
          <ElapsedTimer startedAt={startedAt} stoppedAt={stoppedAt} />

          {failed && (
            <ErrorPanel
              step={failedStep ?? 'analysis'}
              error={error}
              onRetry={onRetry}
              onNewVideo={onNewVideo}
            />
          )}
        </div>
      </div>
    </main>
  )
}

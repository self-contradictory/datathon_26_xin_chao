import type { ReactNode } from 'react'
import { showsViolations } from '@/api/types'
import type { BatchStage } from '@/batch/types'
import {
  CheckCircleIcon,
  ErrorIcon,
  PendingIcon,
  SpinnerIcon,
} from '@/components/icons'
import { useErrorText } from '@/components/processing/errorText'
import { uploadPercent } from '@/components/processing/steps'
import { format, useStrings } from '@/i18n'

function StatusLine({
  icon,
  children,
}: {
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <p className="flex items-start gap-2">
      <span aria-hidden="true" className="size-6 shrink-0">
        {icon}
      </span>
      <span className="min-w-0">{children}</span>
    </p>
  )
}

function FailedStatus({
  stage,
}: {
  stage: Extract<BatchStage, { kind: 'failed' }>
}) {
  const { title, text } = useErrorText(stage.step, stage.error)
  return (
    <StatusLine icon={<ErrorIcon className="text-text" />}>
      <span className="font-semibold">{title}</span>
      <span className="block text-text-muted">{text}</span>
    </StatusLine>
  )
}

function UploadStatus({
  progress,
  fileName,
}: {
  progress: number
  fileName: string
}) {
  const t = useStrings('batchRow')
  const percent = uploadPercent(progress)
  return (
    <div className="flex flex-col gap-2">
      <StatusLine icon={<SpinnerIcon />}>
        {format(t.uploading, { percent })}
      </StatusLine>
      <div
        role="progressbar"
        aria-label={format(t.progress, { name: fileName })}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="h-1 overflow-hidden rounded-full bg-border"
      >
        <div
          className="h-full rounded-full bg-brand transition-[width] duration-150 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}

export function RowStatus({
  stage,
  fileName,
}: {
  stage: BatchStage
  fileName: string
}) {
  const t = useStrings('batchRow')
  const verdict = useStrings('verdictSummary')

  switch (stage.kind) {
    case 'queued':
      return (
        <StatusLine icon={<PendingIcon className="text-text-muted" />}>
          <span className="text-text-muted">{t.queued}</span>
        </StatusLine>
      )
    case 'uploading':
      return <UploadStatus progress={stage.progress} fileName={fileName} />
    case 'analyzing':
      return <StatusLine icon={<SpinnerIcon />}>{t.analyzing}</StatusLine>
    case 'done':
      return showsViolations(stage.job) ? (
        <StatusLine icon={<ErrorIcon className="text-danger" />}>
          <span className="font-semibold text-danger-text">
            {format(verdict.violation, { n: stage.job.violations.length })}
          </span>
        </StatusLine>
      ) : (
        <StatusLine icon={<CheckCircleIcon className="text-success" />}>
          <span className="font-semibold text-success-text">
            {verdict.clean}
          </span>
        </StatusLine>
      )
    case 'failed':
      return <FailedStatus stage={stage} />
  }
}

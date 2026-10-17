import type { ReactNode } from 'react'
import { useStrings } from '@/i18n'
import {
  CheckCircleIcon,
  ErrorIcon,
  PendingIcon,
  SpinnerIcon,
} from '@/components/icons'
import { STEPS, uploadPercent, type StepKey, type StepState } from './steps'

const ICONS: Record<StepState, ReactNode> = {
  done: <CheckCircleIcon className="text-success" />,
  active: <SpinnerIcon />,
  error: <ErrorIcon className="text-text" />,
  pending: <PendingIcon className="text-text-muted" />,
}

const LABEL_CLASS: Record<StepState, string> = {
  done: 'text-text',
  active: 'font-semibold text-text',
  error: 'font-semibold text-text',
  pending: 'text-text-muted',
}

export function StepList({
  states,
  uploadProgress,
}: {
  states: Record<StepKey, StepState>
  uploadProgress: number
}) {
  const t = useStrings('stepList')
  const names = useStrings('steps')
  const percent = uploadPercent(uploadProgress)

  return (
    <ol aria-label={t.list} className="flex flex-col">
      {STEPS.map((key) => {
        const state = states[key]
        const showProgress = key === 'upload' && state === 'active'
        return (
          <li key={key} className="flex gap-4 border-b border-border py-3">
            <span aria-hidden="true" className="size-6 shrink-0">
              {ICONS[state]}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <div className="flex justify-between gap-3">
                <span className={LABEL_CLASS[state]}>{names[key]}</span>
                <span className="text-secondary leading-6 whitespace-nowrap text-text-muted tabular-nums">
                  {showProgress ? `${percent}%` : t[state]}
                </span>
              </div>
              {showProgress && (
                <div
                  role="progressbar"
                  aria-label={t.progress}
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
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

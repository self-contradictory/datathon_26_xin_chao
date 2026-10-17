import type { JobErrorKind } from '@/api/source'
import { Button } from '@/components/Button'
import { ErrorIcon } from '@/components/icons'
import { useStrings } from '@/i18n'
import { useErrorText } from './errorText'
import type { StepKey } from './steps'

export function ErrorPanel({
  step,
  error,
  onRetry,
  onNewVideo,
}: {
  step: StepKey
  error: JobErrorKind | null
  onRetry: () => void
  onNewVideo: () => void
}) {
  const t = useStrings('errorPanel')
  const { title, text } = useErrorText(step, error)

  return (
    <div className="flex flex-col gap-4 rounded-md border border-text p-4">
      <div role="alert" className="flex gap-3">
        <ErrorIcon className="shrink-0 text-text" />
        <div className="flex min-w-0 flex-col gap-1">
          <p className="font-semibold">{title}</p>
          <p className="text-text-muted">{text}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3 sm:pl-9">
        <Button onClick={onRetry} className="max-sm:w-full">
          {t.retry}
        </Button>
        <Button
          variant="secondary"
          onClick={onNewVideo}
          className="max-sm:w-full"
        >
          {t.newVideo}
        </Button>
      </div>
    </div>
  )
}

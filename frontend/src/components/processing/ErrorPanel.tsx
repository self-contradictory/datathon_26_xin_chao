import type { JobErrorKind } from '@/api/source'
import { Button } from '@/components/Button'
import { ErrorIcon } from '@/components/icons'
import { POLL_TIMEOUT_MS } from '@/config'
import { format, useStrings, type Messages } from '@/i18n'
import type { StepKey } from './steps'

type MessageKey = Exclude<
  keyof Messages['errorPanel'],
  'title' | 'retry' | 'newVideo'
>

const MESSAGE_BY_KIND: Record<JobErrorKind, MessageKey> = {
  failed: 'failed',
  timeout: 'timeout',
  network: 'network',
  unauthorized: 'unauthorized',
  not_found: 'notFound',
  bad_file: 'badFile',
  server: 'server',
  bad_response: 'server',
}

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
  const names = useStrings('steps')

  return (
    <div className="flex flex-col gap-4 rounded-md border border-text p-4">
      <div role="alert" className="flex gap-3">
        <ErrorIcon className="shrink-0 text-text" />
        <div className="flex min-w-0 flex-col gap-1">
          <p className="font-semibold">
            {format(t.title, { step: names[step] })}
          </p>
          <p className="text-text-muted">
            {format(t[MESSAGE_BY_KIND[error ?? 'failed']], {
              minutes: POLL_TIMEOUT_MS / 60_000,
            })}
          </p>
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

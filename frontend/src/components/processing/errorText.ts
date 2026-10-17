import type { JobErrorKind } from '@/api/source'
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
  aborted: 'failed',
}

export function useErrorText(step: StepKey, error: JobErrorKind | null) {
  const t = useStrings('errorPanel')
  const names = useStrings('steps')
  return {
    title: format(t.title, { step: names[step] }),
    text: format(t[MESSAGE_BY_KIND[error ?? 'failed']], {
      minutes: POLL_TIMEOUT_MS / 60_000,
    }),
  }
}

import { useRef } from 'react'
import { Button } from '@/components/Button'
import { VideoFileIcon } from '@/components/icons'
import { MONO } from '@/components/styles'
import { format, localeOf, useLang, useStrings } from '@/i18n'
import type { BatchRowView } from '@/screens/contracts'
import { formatFileSize, formatTime } from '@/utils/time'
import { RowStatus } from './RowStatus'

function Thumbnail({ posterUrl }: { posterUrl: string | null }) {
  return (
    <span
      aria-hidden="true"
      className="flex aspect-[9/16] w-10 shrink-0 items-center justify-center overflow-hidden rounded-sm bg-video"
    >
      {posterUrl ? (
        <img src={posterUrl} alt="" className="size-full object-cover" />
      ) : (
        <VideoFileIcon size={20} className="text-text-muted" />
      )}
    </span>
  )
}

export function BatchRow({
  row,
  openRef,
  onOpen,
  onRetry,
}: {
  row: BatchRowView
  openRef?: (button: HTMLButtonElement | null) => void
  onOpen: (id: string) => void
  onRetry: (id: string) => void
}) {
  const t = useStrings('batchRow')
  const errors = useStrings('errorPanel')
  const units = useStrings('units')
  const { lang } = useLang()
  const rowRef = useRef<HTMLLIElement>(null)
  const { id, fileName, fileSize, duration, posterUrl, stage } = row

  function retry() {
    onRetry(id)
    rowRef.current?.focus()
  }

  return (
    <li
      ref={rowRef}
      tabIndex={-1}
      className="flex flex-wrap items-start gap-x-4 gap-y-3 border-b border-border p-4 last:border-b-0 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand"
    >
      <Thumbnail posterUrl={posterUrl} />
      <div className="flex min-w-0 flex-1 basis-56 flex-col gap-2">
        <div className="flex flex-col">
          <p className="font-semibold wrap-anywhere">{fileName}</p>
          <p className="text-secondary text-text-muted">
            <span className={MONO}>
              {formatFileSize(fileSize, localeOf(lang), units)}
            </span>
            {duration !== null && (
              <>
                {' · '}
                <span className={MONO}>{formatTime(duration)}</span>
              </>
            )}
          </p>
        </div>
        <RowStatus stage={stage} fileName={fileName} />
      </div>
      {stage.kind === 'done' && (
        <Button
          ref={openRef}
          variant="secondary"
          aria-label={format(t.openLabel, { name: fileName })}
          onClick={() => onOpen(id)}
          className="max-sm:w-full"
        >
          {t.open}
        </Button>
      )}
      {stage.kind === 'failed' && (
        <Button
          variant="secondary"
          aria-label={format(t.retryLabel, { name: fileName })}
          onClick={retry}
          className="max-sm:w-full"
        >
          {errors.retry}
        </Button>
      )}
    </li>
  )
}

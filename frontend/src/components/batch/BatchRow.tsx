import { useRef } from 'react'
import { Button } from '@/components/Button'
import { CloseIcon, VideoFileIcon } from '@/components/icons'
import { IconButton } from '@/components/report/IconButton'
import { formatShortDate } from '@/utils/time'
import { FileMeta } from '@/components/FileMeta'
import { format, useStrings } from '@/i18n'
import type { BatchRowView } from '@/screens/contracts'
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
  onRemove,
}: {
  row: BatchRowView
  openRef?: (button: HTMLButtonElement | null) => void
  onOpen: (id: string) => void
  onRetry: (id: string) => void
  onRemove?: (id: string) => void
}) {
  const history = useStrings('history')
  const t = useStrings('batchRow')
  const errors = useStrings('errorPanel')
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
          <FileMeta
            size={fileSize}
            duration={duration}
            extra={
              row.date === undefined ? undefined : formatShortDate(row.date)
            }
          />
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
      {onRemove && (
        <IconButton
          label={format(history.remove, { name: fileName })}
          onClick={() => onRemove(id)}
        >
          <CloseIcon size={20} />
        </IconButton>
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

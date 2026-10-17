import { useEffect, useRef } from 'react'
import { batchCounts } from '@/batch/batch'
import { BatchRow } from '@/components/batch/BatchRow'
import { RejectedNotice } from '@/components/batch/RejectedNotice'
import { StartOverControl } from '@/components/batch/StartOverControl'
import { InfoIcon } from '@/components/icons'
import { Owl } from '@/components/Owl'
import { LiveStatus } from '@/components/processing/LiveStatus'
import { format, useStrings } from '@/i18n'
import type { BatchScreenProps } from './contracts'

export function BatchScreen({
  rows,
  rejected,
  pausedBy,
  returnFocusId,
  onOpen,
  onRetry,
  onStartOver,
}: BatchScreenProps) {
  const t = useStrings('batch')
  const titleRef = useRef<HTMLHeadingElement>(null)
  const openButtons = useRef(new Map<string, HTMLButtonElement>())
  const initialFocusId = useRef(returnFocusId)

  useEffect(() => {
    const id = initialFocusId.current
    const button = id ? openButtons.current.get(id) : undefined
    if (button) button.focus()
    else titleRef.current?.focus()
  }, [])

  const counts = batchCounts(rows)
  const pausedRow = rows.find((row) => row.id === pausedBy)
  const progress = format(t.progress, {
    done: counts.finished,
    total: counts.total,
  })
  const announcement =
    counts.unfinished === 0
      ? format(t.announceDone, {
          violations: counts.violations,
          failed: counts.failed,
        })
      : progress

  function openRefFor(id: string) {
    return (button: HTMLButtonElement | null) => {
      if (button) openButtons.current.set(id, button)
      else openButtons.current.delete(id)
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-[848px] flex-col gap-6 px-4 pt-8 pb-12 sm:px-6 lg:pt-12 lg:pb-16">
      <div className="flex flex-col-reverse gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1
            ref={titleRef}
            tabIndex={-1}
            className="text-title font-semibold focus:outline-none"
          >
            {t.title}
          </h1>
          <p className="mt-2 text-section font-semibold tabular-nums">
            {progress}
          </p>
        </div>
        <Owl mood="reading" className="w-44 shrink-0 rounded-lg sm:w-52" />
      </div>
      <LiveStatus message={announcement} />

      <div className="flex flex-col gap-6">
        <div
          aria-live="assertive"
          className={pausedRow ? undefined : 'sr-only'}
        >
          {pausedRow && (
            <div className="flex gap-3 rounded-md bg-surface p-4">
              <InfoIcon className="shrink-0 text-text" />
              <p className="wrap-anywhere">
                {format(t.paused, { name: pausedRow.fileName })}
              </p>
            </div>
          )}
        </div>

        {rejected.length > 0 && <RejectedNotice rejected={rejected} />}

        <ol
          aria-label={t.list}
          className="rounded-md border border-border bg-bg shadow-card"
        >
          {rows.map((row) => (
            <BatchRow
              key={row.id}
              row={row}
              openRef={openRefFor(row.id)}
              onOpen={onOpen}
              onRetry={onRetry}
            />
          ))}
        </ol>

        <StartOverControl
          unfinished={counts.unfinished}
          onConfirm={onStartOver}
        />
      </div>
    </main>
  )
}

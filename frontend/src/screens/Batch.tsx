import { useEffect, useRef } from 'react'
import { batchCounts, isUnfinished } from '@/batch/batch'
import { BatchRow } from '@/components/batch/BatchRow'
import { RejectedNotice } from '@/components/batch/RejectedNotice'
import { StartOverControl } from '@/components/batch/StartOverControl'
import { InfoIcon } from '@/components/icons'
import { LiveStatus } from '@/components/processing/LiveStatus'
import { format, useStrings } from '@/i18n'
import type { BatchScreenProps } from './contracts'

export function BatchScreen({
  rows,
  rejected,
  paused,
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
  const unfinished = rows.filter(isUnfinished).length
  const progress = format(t.progress, {
    done: counts.finished,
    total: counts.total,
  })
  const announcement =
    unfinished === 0
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
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 pt-8 pb-12 sm:px-6 lg:pt-12 lg:pb-16">
      <div className="flex max-w-[72ch] flex-col gap-1">
        <h1
          ref={titleRef}
          tabIndex={-1}
          className="text-title font-semibold focus:outline-none"
        >
          {t.title}
        </h1>
        <p className="text-text-muted">{t.queueNote}</p>
      </div>
      <LiveStatus message={announcement} />

      <div className="flex max-w-[800px] flex-col gap-6">
        <div className="flex flex-col gap-1">
          <p className="text-section font-semibold">{progress}</p>
          <p className="text-secondary text-text-muted">
            {format(t.counts, {
              violations: counts.violations,
              clean: counts.clean,
              failed: counts.failed,
            })}
          </p>
        </div>

        {paused && (
          <div
            role="alert"
            className="flex gap-3 rounded-md border border-text p-4"
          >
            <InfoIcon className="shrink-0 text-text" />
            <p>{t.paused}</p>
          </div>
        )}

        {rejected.length > 0 && <RejectedNotice rejected={rejected} />}

        <ol aria-label={t.list} className="rounded-md border border-border">
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

        <StartOverControl unfinished={unfinished} onConfirm={onStartOver} />
      </div>
    </main>
  )
}

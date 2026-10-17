import { useEffect, useRef, useState } from 'react'
import { isDone } from '@/api/types'
import { BatchRow } from '@/components/batch/BatchRow'
import { Button } from '@/components/Button'
import { ConfirmBar } from '@/components/ConfirmBar'
import { Owl } from '@/components/Owl'
import { checkStore } from '@/history/store'
import type { CheckRecord } from '@/history/types'
import { useStrings } from '@/i18n'
import type { BatchRowView } from './contracts'

function toRow(record: CheckRecord): BatchRowView | null {
  if (!isDone(record.result)) return null
  return {
    id: record.jobId,
    fileName: record.fileName,
    fileSize: record.fileSize,
    duration: record.duration ?? null,
    posterUrl: record.poster ?? null,
    stage: { kind: 'done', job: record.result, checkedAt: record.createdAt },
    date: record.createdAt,
  }
}

function ClearControl({ onConfirm }: { onConfirm: () => void }) {
  const t = useStrings('history')
  const [asking, setAsking] = useState(false)
  const clearRef = useRef<HTMLButtonElement>(null)
  const wasAsking = useRef(false)

  useEffect(() => {
    if (!asking && wasAsking.current) clearRef.current?.focus()
    wasAsking.current = asking
  }, [asking])

  if (!asking) {
    return (
      <Button
        ref={clearRef}
        variant="secondary"
        onClick={() => setAsking(true)}
        className="self-start max-sm:w-full"
      >
        {t.clear}
      </Button>
    )
  }

  return (
    <ConfirmBar
      question={t.confirmClear}
      keepLabel={t.confirmNo}
      confirmLabel={t.confirmYes}
      onKeep={() => setAsking(false)}
      onConfirm={onConfirm}
    />
  )
}

export function HistoryPage() {
  const t = useStrings('history')
  const [rows, setRows] = useState<BatchRowView[] | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let live = true
    checkStore
      .list()
      .then((records) => {
        if (live) setRows(records.map(toRow).filter((row) => row !== null))
      })
      .catch(() => {
        if (live) setRows([])
      })
    return () => {
      live = false
    }
  }, [version])

  async function remove(jobId: string) {
    await checkStore.remove(jobId)
    setVersion((value) => value + 1)
  }

  async function clear() {
    await checkStore.clear()
    setVersion((value) => value + 1)
  }

  function open(jobId: string) {
    window.location.hash = `#/check/${encodeURIComponent(jobId)}`
  }

  return (
    <main className="mx-auto flex w-full max-w-[848px] flex-col gap-6 px-4 pt-8 pb-12 sm:px-6 lg:pt-12 lg:pb-16">
      <h1 className="text-title font-semibold">{t.title}</h1>
      {rows !== null && rows.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-8 text-center">
          <Owl mood="reading" className="w-56 rounded-lg" />
          <p className="text-section font-semibold">{t.empty}</p>
        </div>
      )}
      {rows !== null && rows.length > 0 && (
        <>
          <ol
            aria-label={t.title}
            className="rounded-lg border border-border bg-bg shadow-card"
          >
            {rows.map((row) => (
              <BatchRow
                key={row.id}
                row={row}
                onOpen={open}
                onRetry={() => {}}
                onRemove={(id) => void remove(id)}
              />
            ))}
          </ol>
          <ClearControl onConfirm={() => void clear()} />
        </>
      )}
    </main>
  )
}

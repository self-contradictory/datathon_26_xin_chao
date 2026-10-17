import { useEffect, useState } from 'react'
import { Template } from '@/components/Template'
import { useStrings } from '@/i18n'
import { formatTime } from '@/utils/time'

function useNow(running: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [running])
  return now
}

export function ElapsedTimer({
  startedAt,
  stoppedAt,
}: {
  startedAt: number
  stoppedAt: number | null
}) {
  const t = useStrings('elapsedTimer')
  const now = useNow(stoppedAt === null)
  const elapsedSec = ((stoppedAt ?? now) - startedAt) / 1000
  const template = stoppedAt === null ? t.running : t.stopped

  return (
    <p className="rounded-md bg-surface px-4 py-3 text-text-muted">
      <Template
        text={template}
        values={{
          time: (
            <span className="font-medium text-text tabular-nums">
              {formatTime(elapsedSec)}
            </span>
          ),
        }}
      />
    </p>
  )
}

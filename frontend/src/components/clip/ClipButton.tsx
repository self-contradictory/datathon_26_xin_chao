import { useEffect, useRef, useState } from 'react'
import type { Violation } from '@/api/types'
import { DownloadIcon } from '@/components/icons'
import { useViolationText } from '@/components/report/violationText'
import { format, useStrings } from '@/i18n'
import { saveBlob } from '@/utils/download'
import { formatTime } from '@/utils/time'
import { clipFileName } from './clip'
import { clipFormat, recordClip } from './recordClip'

const RING = 2 * Math.PI * 9

export function ClipButton({
  violation,
  videoUrl,
  fileName,
}: {
  violation: Violation
  videoUrl: string
  fileName: string
}) {
  const t = useStrings('clip')
  const { typeName } = useViolationText()
  const [progress, setProgress] = useState<number | null>(null)
  const [failed, setFailed] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const [supported] = useState(() => clipFormat() !== null)

  useEffect(() => () => abort.current?.abort(), [])

  if (!supported) return null

  async function record() {
    const controller = new AbortController()
    abort.current = controller
    setFailed(false)
    setProgress(0)
    const time = formatTime(violation.timecode_sec)
    try {
      const { blob, ext } = await recordClip(
        videoUrl,
        violation.timecode_sec,
        { type: typeName(violation.type), time },
        setProgress,
        controller.signal,
      )
      saveBlob(clipFileName(fileName, time, ext), blob)
    } catch {
      if (!controller.signal.aborted) setFailed(true)
    } finally {
      if (!controller.signal.aborted) setProgress(null)
    }
  }

  const busy = progress !== null
  const label = busy
    ? format(t.recording, { percent: Math.round((progress ?? 0) * 100) })
    : failed
      ? t.failed
      : t.download

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-busy={busy}
      disabled={busy}
      onClick={() => void record()}
      className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-border bg-bg text-text transition-colors duration-150 ease-out hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-wait"
    >
      {busy ? (
        <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24">
          <circle
            cx="12"
            cy="12"
            r="9"
            fill="none"
            strokeWidth="2.5"
            className="stroke-border"
          />
          <circle
            cx="12"
            cy="12"
            r="9"
            fill="none"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeDasharray={RING}
            strokeDashoffset={RING * (1 - (progress ?? 0))}
            transform="rotate(-90 12 12)"
            className="stroke-brand"
          />
        </svg>
      ) : (
        <DownloadIcon size={20} />
      )}
    </button>
  )
}

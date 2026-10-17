import { IconButton } from '@/components/IconButton'
import { useState } from 'react'
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
  const [supported] = useState(() => clipFormat() !== null)

  if (!supported) return null

  async function record() {
    setFailed(false)
    setProgress(0)
    const time = formatTime(violation.timecode_sec)
    try {
      const { blob, ext } = await recordClip(
        videoUrl,
        violation.timecode_sec,
        { type: typeName(violation.type), time },
        setProgress,
        new AbortController().signal,
      )
      saveBlob(clipFileName(fileName, time, ext), blob)
    } catch {
      setFailed(true)
    } finally {
      setProgress(null)
    }
  }

  const busy = progress !== null
  const label = busy
    ? format(t.recording, { percent: Math.round((progress ?? 0) * 100) })
    : failed
      ? t.failed
      : t.download

  return (
    <IconButton
      label={label}
      aria-busy={busy}
      disabled={busy}
      onClick={() => void record()}
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
    </IconButton>
  )
}

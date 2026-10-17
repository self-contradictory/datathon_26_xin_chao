import { useEffect, useState } from 'react'
import { isDone, showsViolations, type DoneJob } from '@/api/types'
import { Button } from '@/components/Button'
import { ChevronLeftIcon } from '@/components/icons'
import { Owl } from '@/components/Owl'
import { checkStore } from '@/history/store'
import type { CheckRecord } from '@/history/types'
import { useStrings } from '@/i18n'
import { jpegDataUrl } from '@/utils/frames'
import { ReportScreen } from './Report'

interface Loaded {
  record: CheckRecord
  job: DoneJob
  videoUrl: string | null
}

function firstFrame(job: DoneJob): string | null {
  if (!showsViolations(job)) return null
  const frame = job.violations[0]?.evidence_frames[0]
  return frame ? jpegDataUrl(frame.image_base64) : null
}

export function HistoryReport({
  jobId,
  onRecheck,
}: {
  jobId: string
  onRecheck: (file: File) => void
}) {
  const t = useStrings('history')
  const report = useStrings('report')
  const [loaded, setLoaded] = useState<Loaded | null | undefined>(undefined)

  useEffect(() => {
    let live = true
    let url: string | null = null
    checkStore
      .get(jobId)
      .then((record) => {
        if (!live) return
        if (!record || !isDone(record.result)) {
          setLoaded(null)
          return
        }
        url = record.video ? URL.createObjectURL(record.video) : null
        setLoaded({ record, job: record.result, videoUrl: url })
      })
      .catch(() => {
        if (live) setLoaded(null)
      })
    return () => {
      live = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [jobId])

  if (loaded === undefined) return null

  if (loaded === null) {
    return (
      <main className="mx-auto flex max-w-[848px] flex-col items-center gap-4 px-4 py-16 text-center">
        <Owl mood="reading" className="w-40 rounded-lg" />
        <p className="text-section font-semibold">{t.missing}</p>
        <Button
          variant="secondary"
          icon={<ChevronLeftIcon size={20} />}
          onClick={() => {
            window.location.hash = '#/history'
          }}
        >
          {report.backToHistory}
        </Button>
      </main>
    )
  }

  const { record, job, videoUrl } = loaded
  const video = record.video
  return (
    <ReportScreen
      key={record.jobId}
      job={job}
      fileName={record.fileName}
      fileSize={record.fileSize}
      duration={record.duration ?? null}
      videoUrl={videoUrl}
      posterUrl={record.poster ?? firstFrame(job)}
      checkedAt={record.createdAt}
      file={null}
      savedAt={record.createdAt}
      onRecheck={
        video
          ? () =>
              onRecheck(
                new File([video], record.fileName, { type: video.type }),
              )
          : undefined
      }
      exit={{
        kind: 'history',
        onClick: () => {
          window.location.hash = '#/history'
        },
      }}
    />
  )
}

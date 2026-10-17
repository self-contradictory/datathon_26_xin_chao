import type { DoneJob } from '@/api/types'
import { useStrings } from '@/i18n'
import { jpegDataUrl } from '@/utils/frames'
import { RULES } from '@/rules'
import { ProcessingScreen } from '@/screens/Processing'
import { ReportScreen } from '@/screens/Report'
import { UploadScreen } from '@/screens/Upload'
import { X17, X3 } from './sampleFrames'
import type { ProcessingPhase } from '@/screens/contracts'

const noop = () => {}
const datasetUrl = (name: string) => `/__dataset/${encodeURIComponent(name)}`
const CHECKED_AT = Date.parse('2026-10-17T14:05:00+05:00')

const frames = X17.frames.map((frame) => ({
  timestamp_sec: frame.time,
  image_base64: frame.base64,
}))

const ONE: DoneJob = {
  job_id: 'demo-one',
  status: 'done',
  verdict: 'violation',
  violations: [
    {
      type: RULES[0]!.type,
      timecode_sec: 7,
      description:
        'Кассир опускает руки с пачкой купюр ниже края стола. 2 секунды руки и купюры не видны в кадре.',
      evidence_frames: frames,
    },
  ],
}

const TWO: DoneJob = {
  job_id: 'demo-two',
  status: 'done',
  verdict: 'violation',
  violations: [
    ONE.violations[0]!,
    {
      type: RULES[1]!.type,
      timecode_sec: 11.5,
      description: 'Второй человек стоит рядом с открытым денежным ящиком.',
      evidence_frames: frames.slice(1),
    },
  ],
}

const UNKNOWN_TYPE: DoneJob = {
  job_id: 'demo-unknown',
  status: 'done',
  verdict: 'violation',
  violations: [
    { ...ONE.violations[0]!, type: 'Тип, которого нет в словаре правил' },
  ],
}

const CLEAN: DoneJob = {
  job_id: 'demo-clean',
  status: 'done',
  verdict: 'no_violation',
  violations: [],
}

function processing(
  phase: ProcessingPhase,
  elapsedSec: number,
  progress: number,
) {
  const startedAt = Date.now() - elapsedSec * 1000
  return (
    <ProcessingScreen
      fileName={X17.name}
      fileSize={X17.size}
      duration={X17.duration}
      posterUrl={jpegDataUrl(X17.poster)}
      phase={phase}
      uploadProgress={progress}
      startedAt={startedAt}
      stoppedAt={phase === 'failed' ? Date.now() : null}
      error={phase === 'failed' ? 'failed' : null}
      failedStep={phase === 'failed' ? 'analysis' : null}
      onRetry={noop}
      onNewVideo={noop}
    />
  )
}

function report(
  job: DoneJob,
  video: {
    name: string
    size: number
    duration: number
    poster: string
  } | null,
) {
  return (
    <ReportScreen
      job={job}
      fileName={video?.name ?? 'Х-17.mov'}
      fileSize={video?.size ?? null}
      duration={video?.duration ?? null}
      videoUrl={video ? datasetUrl(video.name) : null}
      posterUrl={video ? jpegDataUrl(video.poster) : null}
      checkedAt={CHECKED_AT}
      onNewVideo={noop}
    />
  )
}

const STATES: Record<string, () => React.ReactNode> = {
  'upload-empty': () => <UploadScreen onSubmit={noop} />,
  'upload-dragover': () => (
    <UploadScreen
      onSubmit={noop}
      preview={{ state: 'dragover', fileName: X17.name, fileSize: X17.size }}
    />
  ),
  'upload-error': () => (
    <UploadScreen
      onSubmit={noop}
      preview={{ state: 'error', fileName: 'Х-17.mp4' }}
    />
  ),
  'processing-uploading': () => processing('uploading', 2, 0.4),
  'processing-analyzing': () => processing('analyzing', 48, 1),
  'processing-error': () => processing('failed', 48, 1),
  'report-one': () => report(ONE, X17),
  'report-two': () => report(TWO, X17),
  'report-clean': () => report(CLEAN, X3),
  'report-unknown-type': () => report(UNKNOWN_TYPE, X17),
  'report-no-video': () => report(ONE, null),
}

export default function DemoPage({ state }: { state: string }) {
  const t = useStrings('demo')
  const render = STATES[state]
  if (render) return <>{render()}</>
  return (
    <main className="mx-auto max-w-[1200px] px-6 py-8">
      <h1 className="text-title font-semibold">{t.title}</h1>
      <ul className="mt-4 list-disc pl-6">
        {Object.keys(STATES).map((name) => (
          <li key={name}>
            <a className="text-brand" href={`#/demo/${name}`}>
              {name}
            </a>
          </li>
        ))}
      </ul>
    </main>
  )
}

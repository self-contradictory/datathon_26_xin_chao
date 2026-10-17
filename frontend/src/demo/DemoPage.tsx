import type { DoneJob } from '@/api/types'
import type { BatchStage } from '@/batch/types'
import { useStrings } from '@/i18n'
import { jpegDataUrl } from '@/utils/frames'
import { RULES } from '@/rules'
import { BatchScreen } from '@/screens/Batch'
import { ProcessingScreen } from '@/screens/Processing'
import { ReportScreen } from '@/screens/Report'
import { UploadScreen } from '@/screens/Upload'
import { X17, X3 } from './sampleFrames'
import type {
  BatchRowView,
  BatchScreenProps,
  ProcessingPhase,
  ReportExit,
} from '@/screens/contracts'

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

interface SampleVideo {
  name: string
  size: number
  duration: number
  poster: string
}

function report(
  job: DoneJob,
  video: SampleVideo | null,
  exit: ReportExit['kind'] = 'newVideo',
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
      exit={{ kind: exit, onClick: noop }}
    />
  )
}

function row(
  id: string,
  video: SampleVideo,
  stage: BatchStage,
  fileName = video.name,
): BatchRowView {
  const sample = fileName === video.name
  return {
    id,
    fileName,
    fileSize: video.size,
    duration: sample ? video.duration : null,
    posterUrl: sample ? jpegDataUrl(video.poster) : null,
    stage,
  }
}

const done = (job: DoneJob): BatchStage => ({
  kind: 'done',
  job,
  checkedAt: CHECKED_AT,
})

const queued: BatchStage = { kind: 'queued', jobId: null }

function batch(rows: BatchRowView[], extra: Partial<BatchScreenProps> = {}) {
  return (
    <BatchScreen
      rows={rows}
      rejected={[]}
      paused={false}
      returnFocusId={null}
      onOpen={noop}
      onRetry={noop}
      onStartOver={noop}
      {...extra}
    />
  )
}

const STATES: Record<string, () => React.ReactNode> = {
  'upload-empty': () => <UploadScreen onSubmit={noop} onSubmitMany={noop} />,
  'upload-dragover': () => (
    <UploadScreen
      onSubmit={noop}
      onSubmitMany={noop}
      preview={{ state: 'dragover', fileName: X17.name, fileSize: X17.size }}
    />
  ),
  'upload-error': () => (
    <UploadScreen
      onSubmit={noop}
      onSubmitMany={noop}
      preview={{ state: 'error', fileName: 'Х-17.mp4' }}
    />
  ),
  'upload-too-many': () => (
    <UploadScreen
      onSubmit={noop}
      onSubmitMany={noop}
      preview={{ state: 'too_many', count: 14 }}
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
  'batch-running': () =>
    batch([
      row('a', X17, done(ONE)),
      row('b', X3, done(CLEAN)),
      row('c', X17, { kind: 'uploading', progress: 0.4 }, 'Х-21.mov'),
      row('d', X17, queued, 'Х-22.mov'),
      row('e', X3, queued, 'Х-23.mov'),
    ]),
  'batch-paused': () =>
    batch(
      [
        row('a', X3, done(CLEAN)),
        row('b', X17, {
          kind: 'failed',
          error: 'network',
          step: 'upload',
          jobId: null,
        }),
        row('c', X17, queued, 'Х-21.mov'),
        row('d', X3, queued, 'Х-22.mov'),
      ],
      { paused: true },
    ),
  'batch-done': () =>
    batch(
      [
        row('a', X17, done(TWO)),
        row('b', X3, done(CLEAN)),
        row(
          'c',
          X17,
          { kind: 'failed', error: 'timeout', step: 'analysis', jobId: 'j' },
          'Х-21.mov',
        ),
      ],
      {
        rejected: [
          {
            fileName: 'Х-5.mp4',
            problem: { kind: 'not_mov', extension: 'mp4' },
          },
          { fileName: 'Х-6.mov', problem: { kind: 'empty' } },
        ],
      },
    ),
  'batch-report': () => report(ONE, X17, 'backToList'),
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

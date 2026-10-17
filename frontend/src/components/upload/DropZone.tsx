import { useId, useRef, useState, type ChangeEvent } from 'react'
import { Button } from '@/components/Button'
import {
  DropIcon,
  ErrorIcon,
  UploadIcon,
  VideoFileIcon,
} from '@/components/icons'
import { format, localeOf, useLang, useStrings, type Messages } from '@/i18n'
import { checkVideoFile, type FileProblem } from '@/utils/file'
import { formatFileSize } from '@/utils/time'
import type { UploadScreenProps } from '@/screens/contracts'
import { useFileDrop } from './useFileDrop'

type Strings = Messages['dropZone']

const VIDEO_EXTENSIONS = new Set([
  '3gp',
  'avi',
  'flv',
  'm2ts',
  'm4v',
  'mkv',
  'mp4',
  'mpeg',
  'mpg',
  'mts',
  'ogv',
  'webm',
  'wmv',
])

interface Rejection {
  id: number
  fileName: string
  problem: FileProblem
}

type HeldFile = { fileName: string; fileSize: number }

function rejectionFromPreview(
  preview: UploadScreenProps['preview'],
): Rejection | null {
  if (preview?.state !== 'error') return null
  const problem = checkVideoFile({ name: preview.fileName, size: 0 }) ?? {
    kind: 'empty',
  }
  return { id: 0, fileName: preview.fileName, problem }
}

function describe(t: Strings, { fileName, problem }: Rejection) {
  if (problem.kind === 'empty') {
    return {
      title: t.emptyTitle,
      text: format(t.emptyText, { name: fileName }),
    }
  }
  const ext = problem.extension
  const template = !ext
    ? t.noExtension
    : VIDEO_EXTENSIONS.has(ext)
      ? t.otherVideo
      : t.otherFile
  return {
    title: t.formatTitle,
    text: format(template, { name: fileName, ext }),
  }
}

function IdlePrompt({ t }: { t: Strings }) {
  return (
    <>
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full bg-surface text-text-muted"
      >
        <UploadIcon />
      </span>
      <div className="hidden flex-col gap-1 sm:flex">
        <p className="text-section font-semibold">{t.dropHere}</p>
        <p className="text-text-muted">{t.or}</p>
      </div>
    </>
  )
}

function DragPrompt({ t, file }: { t: Strings; file: HeldFile | null }) {
  const { lang } = useLang()
  const units = useStrings('units')
  return (
    <>
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full bg-brand text-white"
      >
        <DropIcon />
      </span>
      <p className="text-section font-semibold">{t.release}</p>
      {file && (
        <p className="inline-flex min-h-11 max-w-full items-center gap-3 rounded-md border border-border bg-bg px-4 py-2">
          <VideoFileIcon size={20} className="shrink-0 text-text-muted" />
          <span className="min-w-0 wrap-anywhere">{file.fileName}</span>
          <span className="shrink-0 font-mono text-secondary font-medium text-text-muted tabular-nums">
            {formatFileSize(file.fileSize, localeOf(lang), units)}
          </span>
        </p>
      )}
      <p className="text-secondary text-text-muted">{t.onlyMov}</p>
    </>
  )
}

function RejectionAlert({
  t,
  rejection,
  textId,
}: {
  t: Strings
  rejection: Rejection
  textId: string
}) {
  const { title, text } = describe(t, rejection)
  return (
    <div role="alert" className="flex flex-col items-center gap-2">
      <p className="flex flex-col items-center gap-2 text-section font-semibold sm:flex-row">
        <ErrorIcon className="shrink-0" />
        {title}
      </p>
      <p id={textId} className="max-w-[520px] wrap-anywhere text-text-muted">
        {text}
      </p>
    </div>
  )
}

export function DropZone({ onSubmit, preview }: UploadScreenProps) {
  const t = useStrings('dropZone')
  const inputRef = useRef<HTMLInputElement>(null)
  const hintId = useId()
  const errorId = useId()
  const [rejection, setRejection] = useState(() =>
    rejectionFromPreview(preview),
  )

  const previewKey = preview ? `${preview.state}:${preview.fileName}` : ''
  const [shownPreview, setShownPreview] = useState(previewKey)
  if (previewKey !== shownPreview) {
    setShownPreview(previewKey)
    setRejection(rejectionFromPreview(preview))
  }

  function take(file: File) {
    const problem = checkVideoFile(file)
    if (!problem) {
      setRejection(null)
      onSubmit(file)
      return
    }
    setRejection((prev) => ({
      id: (prev?.id ?? 0) + 1,
      fileName: file.name,
      problem,
    }))
  }

  const drop = useFileDrop(take)
  const held: HeldFile | null = preview?.state === 'dragover' ? preview : null
  const dragging = drop.dragging || held !== null

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) take(file)
  }

  const look = dragging
    ? 'border-dashed border-brand bg-brand-tint [&_*]:pointer-events-none'
    : rejection
      ? 'border-solid border-text bg-bg'
      : 'border-dashed border-border bg-bg'

  return (
    <section
      aria-label={t.region}
      {...drop.handlers}
      className={`relative w-full max-w-[640px] rounded-lg border-2 px-4 text-center transition-colors duration-150 sm:px-6 ${rejection ? 'py-10' : 'py-12'} ${look}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".mov,video/quicktime"
        hidden
        onChange={onPick}
      />
      <div
        className={`flex flex-col items-center gap-4 ${dragging ? 'opacity-0' : ''}`}
      >
        {rejection ? (
          <RejectionAlert
            key={rejection.id}
            t={t}
            rejection={rejection}
            textId={errorId}
          />
        ) : (
          <IdlePrompt t={t} />
        )}
        <Button
          aria-describedby={rejection ? errorId : hintId}
          className="px-6"
          onClick={() => inputRef.current?.click()}
        >
          {rejection ? t.chooseAnother : t.choose}
        </Button>
        <p
          id={hintId}
          className={`text-secondary text-text-muted ${rejection ? 'hidden sm:block' : ''}`}
        >
          {rejection ? t.dropAgain : t.onlyMov}
        </p>
      </div>
      {dragging && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 px-4 sm:px-6">
          <DragPrompt t={t} file={held} />
        </div>
      )}
    </section>
  )
}

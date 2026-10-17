import { useId, useRef, useState, type ChangeEvent } from 'react'
import { Button } from '@/components/Button'
import {
  DropIcon,
  ErrorIcon,
  UploadIcon,
  VideoFileIcon,
} from '@/components/icons'
import { MAX_BATCH_FILES } from '@/config'
import { format, localeOf, useLang, useStrings, type Messages } from '@/i18n'
import { checkVideoFile, pickVideos } from '@/utils/file'
import { formatFileSize } from '@/utils/time'
import type { UploadScreenProps } from '@/screens/contracts'
import { Mascot } from './Mascot'
import { describeRejection, type RejectionReason } from './rejection'
import { useFileDrop } from './useFileDrop'

type Strings = Messages['dropZone']

type Rejection = RejectionReason & { id: number }

type HeldFile = { fileName: string; fileSize: number }

function reasonFromPreview(
  preview: UploadScreenProps['preview'],
): RejectionReason | null {
  if (preview?.state === 'too_many') {
    return { kind: 'too_many', count: preview.count, max: MAX_BATCH_FILES }
  }
  if (preview?.state !== 'error') return null
  const problem = checkVideoFile({ name: preview.fileName, size: 0 }) ?? {
    kind: 'empty',
  }
  return { kind: 'file', fileName: preview.fileName, problem }
}

function rejectionFromPreview(
  preview: UploadScreenProps['preview'],
): Rejection | null {
  const reason = reasonFromPreview(preview)
  return reason && { ...reason, id: 0 }
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
      <p className="text-secondary text-text-muted">
        {format(t.hint, { max: MAX_BATCH_FILES })}
      </p>
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
  const { title, text } = describeRejection(t, rejection)
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

export function DropZone({
  onSubmit,
  onSubmitMany,
  preview,
}: UploadScreenProps) {
  const t = useStrings('dropZone')
  const inputRef = useRef<HTMLInputElement>(null)
  const hintId = useId()
  const errorId = useId()
  const [rejection, setRejection] = useState(() =>
    rejectionFromPreview(preview),
  )

  const previewKey = preview ? JSON.stringify(preview) : ''
  const [shownPreview, setShownPreview] = useState(previewKey)
  if (previewKey !== shownPreview) {
    setShownPreview(previewKey)
    setRejection(rejectionFromPreview(preview))
  }

  function reject(reason: RejectionReason) {
    setRejection((prev) => ({ ...reason, id: (prev?.id ?? 0) + 1 }))
  }

  function takeOne(file: File) {
    const problem = checkVideoFile(file)
    if (problem) {
      reject({ kind: 'file', fileName: file.name, problem })
      return
    }
    setRejection(null)
    onSubmit(file)
  }

  function take(files: File[]) {
    if (files.length === 0) return
    const pick = pickVideos(files, MAX_BATCH_FILES)
    if (pick.kind === 'single') {
      takeOne(pick.file)
    } else if (pick.kind === 'batch') {
      setRejection(null)
      onSubmitMany(pick.files, pick.rejected)
    } else {
      reject(pick)
    }
  }

  const drop = useFileDrop(take)
  const held: HeldFile | null = preview?.state === 'dragover' ? preview : null
  const dragging = drop.dragging || held !== null

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    take(files)
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
      className={`relative mt-20 w-full max-w-[640px] rounded-lg border-2 px-4 text-center transition-colors duration-150 sm:mt-24 sm:px-6 ${rejection ? 'py-10' : 'py-12'} ${look}`}
    >
      <Mascot excited={dragging} />
      <input
        ref={inputRef}
        type="file"
        accept=".mov,video/quicktime"
        multiple
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
          {rejection ? t.dropAgain : format(t.hint, { max: MAX_BATCH_FILES })}
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

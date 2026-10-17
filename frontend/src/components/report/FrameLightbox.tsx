import {
  useEffect,
  useEffectEvent,
  useId,
  useLayoutEffect,
  useRef,
  type KeyboardEvent,
} from 'react'
import type { EvidenceFrame } from '@/api/types'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CloseIcon,
} from '@/components/icons'
import { format, useStrings } from '@/i18n'
import { jpegDataUrl } from '@/utils/frames'
import { formatFrameTime } from '@/utils/time'
import { IconButton } from './IconButton'
import { MONO } from '@/components/styles'
import { wrapIndex } from '@/utils/wrap'

export function FrameLightbox({
  frames,
  index,
  type,
  opener,
  onIndexChange,
  onClose,
}: {
  frames: readonly EvidenceFrame[]
  index: number
  type: string
  opener: HTMLElement | null
  onIndexChange: (index: number) => void
  onClose: () => void
}) {
  const t = useStrings('frameLightbox')
  const dialogRef = useRef<HTMLDialogElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const titleId = useId()

  useLayoutEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    closeRef.current?.focus()
    return () => {
      if (dialog.open) dialog.close()
      document.body.style.overflow = overflow
      opener?.focus()
    }
  }, [opener])

  const closeOnNavigation = useEffectEvent(onClose)
  useEffect(() => {
    const close = () => closeOnNavigation()
    window.addEventListener('hashchange', close)
    return () => window.removeEventListener('hashchange', close)
  }, [])

  const frame = frames[index]
  if (!frame) return null
  const count = frames.length
  const time = formatFrameTime(frame.timestamp_sec)
  const step = (by: number) => onIndexChange(wrapIndex(index, by, count))

  function onKeyDown(event: KeyboardEvent) {
    if (count < 2) return
    if (event.key === 'ArrowLeft') step(-1)
    else if (event.key === 'ArrowRight') step(1)
    else return
    event.preventDefault()
  }

  return (
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
      onKeyDown={onKeyDown}
      className="fixed inset-0 m-0 size-full max-h-none max-w-none items-center justify-center overflow-auto bg-black/60 p-4 text-text backdrop:bg-transparent open:flex sm:p-6"
    >
      <div className="flex max-w-full flex-col gap-4 rounded-md bg-bg p-4 shadow-lightbox">
        <div className="flex items-center justify-between gap-3">
          <p id={titleId} className="font-semibold">
            <span className={MONO}>{time}</span>
            {' · '}
            {format(t.frameOf, { k: index + 1, n: count })}
          </p>
          <button
            ref={closeRef}
            type="button"
            aria-label={t.close}
            onClick={onClose}
            className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-md text-text transition-colors duration-150 hover:bg-surface focus-visible:outline-2 focus-visible:outline-brand"
          >
            <CloseIcon />
          </button>
        </div>
        <img
          src={jpegDataUrl(frame.image_base64)}
          alt={format(t.alt, { type, k: index + 1, time })}
          className="mx-auto block aspect-[9/16] w-[min(calc(100vw-80px),calc((100dvh-200px)*9/16))] max-w-full rounded-sm bg-video object-contain"
        />
        {count > 1 && (
          <div className="flex justify-between gap-3">
            <IconButton label={t.prev} onClick={() => step(-1)}>
              <ChevronLeftIcon size={20} />
            </IconButton>
            <IconButton label={t.next} onClick={() => step(1)}>
              <ChevronRightIcon size={20} />
            </IconButton>
          </div>
        )}
      </div>
    </dialog>
  )
}

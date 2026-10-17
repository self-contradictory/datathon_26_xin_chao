import { useState } from 'react'
import type { EvidenceFrame } from '@/api/types'
import { format, useStrings } from '@/i18n'
import { jpegDataUrl } from '@/utils/frames'
import { formatFrameTime } from '@/utils/time'
import { FrameLightbox } from './FrameLightbox'

export function EvidenceFrames({
  frames,
  type,
}: {
  frames: readonly EvidenceFrame[]
  type: string
}) {
  const t = useStrings('evidenceFrames')
  const [open, setOpen] = useState<{
    index: number
    opener: HTMLElement
  } | null>(null)

  if (frames.length === 0) return null

  return (
    <>
      <ul
        aria-label={t.frames}
        className="grid grid-cols-2 gap-3 rounded-md bg-surface p-3 min-[360px]:grid-cols-3 sm:grid-cols-[repeat(3,minmax(0,240px))] sm:gap-4 sm:p-4"
      >
        {frames.map((frame, index) => {
          const time = formatFrameTime(frame.timestamp_sec)
          return (
            <li key={index}>
              <figure className="flex flex-col gap-2">
                <button
                  type="button"
                  aria-label={format(t.enlarge, { k: index + 1, time })}
                  onClick={(event) =>
                    setOpen({ index, opener: event.currentTarget })
                  }
                  className="block aspect-[9/16] w-full cursor-zoom-in overflow-hidden rounded-sm bg-video focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                >
                  <img
                    src={jpegDataUrl(frame.image_base64)}
                    alt=""
                    className="size-full object-cover"
                  />
                </button>
                <figcaption className="text-caption text-text-muted">
                  <span className="font-mono font-medium text-text tabular-nums">
                    {time}
                  </span>
                  {' · '}
                  <span className="whitespace-nowrap">
                    {format(t.frame, { k: index + 1 })}
                  </span>
                </figcaption>
              </figure>
            </li>
          )
        })}
      </ul>
      {open && (
        <FrameLightbox
          frames={frames}
          index={open.index}
          type={type}
          opener={open.opener}
          onIndexChange={(index) => setOpen({ ...open, index })}
          onClose={() => setOpen(null)}
        />
      )}
    </>
  )
}

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from 'react'
import { format, useStrings } from '@/i18n'
import { formatTime } from '@/utils/time'
import { MarkerButton } from './MarkerButton'
import { clamp, groupMarkers, tooltipAlign } from './markers'
import type { PlayerMarker } from './types'

const KEY_STEP_SEC = 5
const KNOB_RADIUS_PX = 7

interface ScrubberProps {
  markers: readonly PlayerMarker[]
  activeMarkerId: string | null
  span: number
  current: number
  totalText: string
  available: boolean
  onSeek: (time: number) => void
  onMarkerSelect: (marker: PlayerMarker) => void
}

export function Scrubber({
  markers,
  activeMarkerId,
  span,
  current,
  totalText,
  available,
  onSeek,
  onMarkerSelect,
}: ScrubberProps) {
  const t = useStrings('player')
  const trackRef = useRef<HTMLDivElement>(null)
  const [trackWidth, setTrackWidth] = useState(0)

  useEffect(() => {
    const track = trackRef.current
    if (!track) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setTrackWidth(entry.contentRect.width)
    })
    observer.observe(track)
    return () => observer.disconnect()
  }, [])

  const groups = useMemo(
    () => groupMarkers(markers, span, trackWidth),
    [markers, span, trackWidth],
  )
  const ratio = span > 0 ? clamp(current / span, 0, 1) : 0
  const percent = `${ratio * 100}%`
  const activeGroup = groups.find((group) =>
    group.items.some((item) => item.id === activeMarkerId),
  )
  const onActiveMarker =
    activeGroup !== undefined &&
    Math.abs(activeGroup.ratio - ratio) * trackWidth < KNOB_RADIUS_PX

  function timeAt(clientX: number): number {
    const rect = trackRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return 0
    return clamp((clientX - rect.left) / rect.width, 0, 1) * span
  }

  function startDrag(event: PointerEvent<HTMLElement>) {
    if (!available || event.button !== 0) return
    event.currentTarget.setPointerCapture(event.pointerId)
    onSeek(timeAt(event.clientX))
  }

  function drag(event: PointerEvent<HTMLElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      onSeek(timeAt(event.clientX))
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!available) return
    const targets: Record<string, number> = {
      ArrowLeft: current - KEY_STEP_SEC,
      ArrowDown: current - KEY_STEP_SEC,
      ArrowRight: current + KEY_STEP_SEC,
      ArrowUp: current + KEY_STEP_SEC,
      Home: 0,
      End: span,
    }
    const target = targets[event.key]
    if (target === undefined) return
    event.preventDefault()
    onSeek(clamp(target, 0, span))
  }

  return (
    <div ref={trackRef} className="relative h-6">
      <div
        role="slider"
        tabIndex={available ? 0 : -1}
        aria-label={t.seek}
        aria-valuemin={0}
        aria-valuemax={Math.floor(span)}
        aria-valuenow={Math.floor(Math.min(current, span))}
        aria-valuetext={format(t.position, {
          current: formatTime(current),
          total: totalText,
        })}
        aria-disabled={available ? undefined : true}
        onPointerDown={startDrag}
        onPointerMove={drag}
        onKeyDown={onKeyDown}
        className={`absolute inset-0 touch-none rounded-sm select-none before:absolute before:inset-x-0 before:-top-2.5 before:bottom-0 before:content-[''] focus-visible:outline-2 focus-visible:outline-white ${
          available ? 'cursor-pointer' : ''
        }`}
      >
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-2.5 h-1 rounded-full bg-white/30"
        />
        {available && (
          <div
            aria-hidden="true"
            className="absolute top-2.5 left-0 h-1 rounded-full bg-white/90"
            style={{ width: percent }}
          />
        )}
      </div>

      {groups.map((group) => (
        <MarkerButton
          key={group.first.id}
          group={group}
          active={group === activeGroup}
          align={tooltipAlign(group.ratio, trackWidth)}
          label={format(group.items.length > 1 ? t.markerGroup : t.marker, {
            label: group.first.label,
            time: formatTime(group.first.time),
            more: group.items.length - 1,
          })}
          onSelect={() => onMarkerSelect(group.first)}
        />
      ))}

      {available && (
        <div
          aria-hidden="true"
          onPointerDown={startDrag}
          onPointerMove={drag}
          className="absolute top-1/2 z-20 flex size-6 -translate-1/2 cursor-grab touch-none items-center justify-center active:cursor-grabbing"
          style={{ left: percent }}
        >
          <span
            className={`size-3.5 rounded-full shadow-popover ${
              onActiveMarker ? 'bg-danger ring-2 ring-white' : 'bg-white'
            }`}
          />
        </div>
      )}
    </div>
  )
}

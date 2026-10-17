import { formatTime } from '@/utils/time'
import type { MarkerGroup, TooltipAlign } from './markers'
import { MONO } from '@/components/styles'

const TOOLTIP_POSITION: Record<TooltipAlign, string> = {
  start: 'left-0',
  center: 'left-1/2 -translate-x-1/2',
  end: 'right-0',
}

export function MarkerButton({
  group,
  active,
  label,
  align,
  onSelect,
}: {
  group: MarkerGroup
  active: boolean
  label: string
  align: TooltipAlign
  onSelect: () => void
}) {
  const count = group.items.length

  return (
    <button
      type="button"
      aria-label={label}
      aria-current={active ? 'true' : undefined}
      onClick={onSelect}
      className="group absolute bottom-0 z-10 h-11 w-8 -translate-x-1/2 cursor-pointer rounded-sm focus-visible:outline-2 focus-visible:outline-white"
      style={{ left: `${group.ratio * 100}%` }}
    >
      <span
        aria-hidden="true"
        className={`absolute bottom-3 left-1/2 -translate-x-1/2 translate-y-1/2 rounded-[1px] ring-1 ring-video transition-[width,height] duration-150 ease-out ${
          group.items.every((item) => item.dimmed) ? 'bg-white/60' : 'bg-danger'
        } ${active ? 'h-4 w-1.5' : 'h-3 w-1'}`}
      />
      {count > 1 && (
        <span
          aria-hidden="true"
          className="absolute bottom-[22px] left-1/2 h-4 min-w-4 -translate-x-1/2 rounded-full bg-white px-1 text-caption font-semibold text-text tabular-nums"
        >
          {count}
        </span>
      )}
      <span
        aria-hidden="true"
        className={`absolute bottom-full mb-1 hidden w-max max-w-[240px] rounded-sm bg-bg px-2 py-1 text-left text-caption text-text shadow-popover group-hover:block group-focus-visible:block ${TOOLTIP_POSITION[align]}`}
      >
        {group.items.map((item) => (
          <span key={item.id} className="block">
            <span className={MONO}>{formatTime(item.time)}</span> ·{' '}
            <span>{item.label}</span>
          </span>
        ))}
      </span>
    </button>
  )
}

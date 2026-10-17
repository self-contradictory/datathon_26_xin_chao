import { formatTime } from '@/utils/time'

export function TimeChip({
  seconds,
  onTint = false,
}: {
  seconds: number
  onTint?: boolean
}) {
  return (
    <span
      className={`shrink-0 rounded-sm px-2 text-secondary leading-6 font-medium tabular-nums ${
        onTint ? 'bg-bg' : 'bg-surface'
      }`}
    >
      {formatTime(seconds)}
    </span>
  )
}

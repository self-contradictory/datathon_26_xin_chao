import { format, useStrings } from '@/i18n'
import { formatShortDate } from '@/utils/time'

export function SavedChip({
  savedAt,
  onRecheck,
}: {
  savedAt: number
  onRecheck?: () => void
}) {
  const t = useStrings('history')
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-secondary">
      <span className="rounded-full bg-surface px-3 py-1 font-semibold text-text tabular-nums">
        {format(t.fromHistory, { date: formatShortDate(savedAt) })}
      </span>
      {onRecheck && (
        <button
          type="button"
          onClick={onRecheck}
          className="cursor-pointer rounded-sm font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          {t.recheck}
        </button>
      )}
    </p>
  )
}

import { CheckIcon } from '@/components/icons'
import { Owl } from '@/components/Owl'
import type { ReviewSummary } from '@/history/review'
import { format, useStrings } from '@/i18n'

function ReviewChip({ summary }: { summary: ReviewSummary }) {
  const t = useStrings('review')
  const label = summary.complete
    ? t.complete
    : format(t.progress, { done: summary.reviewed, total: summary.total })
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className="inline-flex h-7 min-w-7 shrink-0 items-center justify-center gap-1 rounded-full bg-bg px-2 text-secondary font-semibold text-text tabular-nums"
    >
      {summary.complete ? (
        <CheckIcon size={20} className="text-text" />
      ) : (
        `${summary.reviewed}/${summary.total}`
      )}
    </span>
  )
}

export function VerdictSummary({
  violation,
  count,
  review,
  className = '',
}: {
  violation: boolean
  count: number
  review?: ReviewSummary
  className?: string
}) {
  const t = useStrings('verdictSummary')

  return (
    <section
      aria-label={t.label}
      className={`flex items-center gap-4 rounded-lg border p-4 shadow-card sm:gap-6 sm:p-6 ${
        violation
          ? 'border-danger/15 bg-danger-tint'
          : 'border-success/15 bg-success-tint'
      } ${className}`}
    >
      {violation ? (
        <Owl mood="warning" className="-my-3 w-24 shrink-0 sm:w-36" />
      ) : (
        <Owl mood="happy" className="-my-3 w-24 shrink-0 sm:w-36" />
      )}
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <p
          className={`text-verdict font-semibold ${
            violation ? 'text-danger-text' : 'text-success-text'
          }`}
        >
          {violation ? format(t.violation, { n: count }) : t.clean}
        </p>
        {violation && review && review.total > 0 && (
          <ReviewChip summary={review} />
        )}
      </div>
    </section>
  )
}

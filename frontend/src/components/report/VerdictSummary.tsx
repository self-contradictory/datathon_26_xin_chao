import { Owl } from '@/components/Owl'
import { format, useStrings } from '@/i18n'

export function VerdictSummary({
  violation,
  count,
  className = '',
}: {
  violation: boolean
  count: number
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
        <Owl mood="warning" className="-my-3 w-28 shrink-0 sm:w-36" />
      ) : (
        <Owl mood="happy" className="-my-3 w-28 shrink-0 sm:w-36" />
      )}
      <div className="flex min-w-0 flex-col gap-3">
        <p
          className={`text-verdict font-semibold ${
            violation ? 'text-danger-text' : 'text-success-text'
          }`}
        >
          {violation ? format(t.violation, { n: count }) : t.clean}
        </p>
      </div>
    </section>
  )
}

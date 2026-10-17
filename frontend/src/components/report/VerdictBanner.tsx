import type { Ref } from 'react'
import { CheckCircleIcon, ErrorIcon } from '@/components/icons'
import { format, localeOf, useLang, useStrings } from '@/i18n'
import { formatFileSize, formatTime } from '@/utils/time'
import { MONO } from '@/components/styles'

export function VerdictBanner({
  violation,
  count,
  fileName,
  fileSize,
  duration,
  checkedAt,
  titleRef,
}: {
  titleRef?: Ref<HTMLHeadingElement>
  violation: boolean
  count: number
  fileName: string
  fileSize: number | null
  duration: number | null
  checkedAt: number
}) {
  const t = useStrings('verdictBanner')
  const units = useStrings('units')
  const locale = localeOf(useLang().lang)
  const checked = new Date(checkedAt).toLocaleString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <section
      aria-label={t.label}
      className={violation ? 'bg-danger-tint' : 'bg-success-tint'}
    >
      <div className="mx-auto flex max-w-[1200px] items-start gap-3 p-4 sm:p-6">
        {violation ? (
          <ErrorIcon className="mt-0.5 shrink-0 text-danger" />
        ) : (
          <CheckCircleIcon className="mt-0.5 shrink-0 text-success" />
        )}
        <div className="flex min-w-0 flex-col gap-1">
          <h1
            ref={titleRef}
            tabIndex={-1}
            className={`text-verdict font-bold outline-none ${
              violation ? 'text-danger-text' : 'text-success-text'
            }`}
          >
            {violation ? format(t.violation, { n: count }) : t.clean}
          </h1>
          <p className="text-secondary wrap-anywhere text-text-muted">
            {fileName}
            {fileSize !== null && (
              <>
                {' · '}
                <span className={MONO}>
                  {formatFileSize(fileSize, locale, units)}
                </span>
              </>
            )}
            {duration !== null && (
              <>
                {' · '}
                <span className={MONO}>{formatTime(duration)}</span>
              </>
            )}
            {' · '}
            {format(t.checked, { date: checked })}
          </p>
        </div>
      </div>
    </section>
  )
}

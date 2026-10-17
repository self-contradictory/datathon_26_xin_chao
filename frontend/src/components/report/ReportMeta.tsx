import { MONO } from '@/components/styles'
import { format, localeOf, useLang, useStrings } from '@/i18n'
import { formatFileSize, formatShortDate, formatTime } from '@/utils/time'

export function ReportMeta({
  fileName,
  fileSize,
  duration,
  checkedAt,
}: {
  fileName: string
  fileSize: number | null
  duration: number | null
  checkedAt: number
}) {
  const t = useStrings('verdictSummary')
  const units = useStrings('units')
  const locale = localeOf(useLang().lang)
  const checked = formatShortDate(checkedAt)

  return (
    <p className="min-w-0 text-secondary wrap-anywhere text-text-muted">
      <span className="font-semibold text-text">{fileName}</span>
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
  )
}

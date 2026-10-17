import { localeOf, useLang, useStrings } from '@/i18n'
import { formatFileSize, formatTime } from '@/utils/time'
import { MONO } from './styles'

export function FileMeta({
  size,
  duration,
}: {
  size: number
  duration: number | null
}) {
  const units = useStrings('units')
  const { lang } = useLang()

  return (
    <p className="text-secondary text-text-muted">
      <span className={MONO}>
        {formatFileSize(size, localeOf(lang), units)}
      </span>
      {duration !== null && (
        <>
          {' · '}
          <span className={MONO}>{formatTime(duration)}</span>
        </>
      )}
    </p>
  )
}

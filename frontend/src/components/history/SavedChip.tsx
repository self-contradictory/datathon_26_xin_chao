import { Button } from '@/components/Button'
import { useStrings } from '@/i18n'

export function SavedChip({ onRecheck }: { onRecheck?: () => void }) {
  const t = useStrings('history')
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="inline-flex h-8 items-center rounded-full bg-surface px-3 text-secondary font-semibold text-text">
        {t.fromHistory}
      </span>
      {onRecheck && (
        <Button variant="secondary" onClick={onRecheck}>
          {t.recheck}
        </Button>
      )}
    </div>
  )
}

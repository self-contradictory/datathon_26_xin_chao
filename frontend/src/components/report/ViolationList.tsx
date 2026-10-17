import type { Violation } from '@/api/types'
import { ChevronRightIcon } from '@/components/icons'
import { TextLink } from '@/components/TextLink'
import { useStrings } from '@/i18n'
import { TimeChip } from './TimeChip'

export function ViolationList({
  violations,
  activeIndex,
  onSelect,
}: {
  violations: readonly Violation[]
  activeIndex: number
  onSelect: (index: number) => void
}) {
  const t = useStrings('violationList')

  return (
    <div className="overflow-hidden rounded-md border border-border bg-bg shadow-card">
      <p className="border-b border-border p-4 text-secondary text-text-muted">
        {t.hint}
      </p>
      <ul>
        {violations.map((violation, index) => {
          const active = index === activeIndex
          return (
            <li key={index} className="border-b border-border">
              <button
                type="button"
                aria-current={active ? 'true' : undefined}
                onClick={() => onSelect(index)}
                className={`flex min-h-14 w-full cursor-pointer items-center gap-3 border-l-[3px] py-3 pr-4 pl-[13px] text-left transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
                  active
                    ? 'border-brand bg-brand-tint'
                    : 'border-transparent bg-bg hover:bg-surface'
                }`}
              >
                <TimeChip seconds={violation.timecode_sec} onTint={active} />
                <span
                  lang="ru"
                  className={`min-w-0 flex-1 wrap-break-word ${active ? 'font-semibold' : ''}`}
                >
                  {violation.type}
                </span>
                <ChevronRightIcon
                  size={20}
                  className="shrink-0 text-text-muted"
                />
              </button>
            </li>
          )
        })}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-secondary text-text-muted">
        <span>{t.whatWeLookFor}</span>
        <TextLink href="#/rules">{t.rules}</TextLink>
      </div>
    </div>
  )
}

export function CleanSummary() {
  const t = useStrings('violationList')

  return (
    <div className="flex max-w-[72ch] flex-col gap-3">
      <p>{t.cleanText}</p>
      <p className="text-text-muted">{t.cleanHint}</p>
      <TextLink href="#/rules">{t.whatWeLookFor}</TextLink>
    </div>
  )
}

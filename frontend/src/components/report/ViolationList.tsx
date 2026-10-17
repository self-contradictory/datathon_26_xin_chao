import { useId } from 'react'
import type { Violation } from '@/api/types'
import { CheckCircleIcon, ChevronRightIcon } from '@/components/icons'
import { TextLink } from '@/components/TextLink'
import { format, useStrings } from '@/i18n'
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
  const titleId = useId()

  return (
    <section
      aria-labelledby={titleId}
      className="overflow-hidden rounded-md border border-border"
    >
      <div className="flex flex-col gap-1 border-b border-border p-4">
        <h2 id={titleId} className="text-section font-semibold">
          {format(t.found, { n: violations.length })}
        </h2>
        <p className="text-secondary text-text-muted">{t.hint}</p>
      </div>
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
    </section>
  )
}

export function CleanSummary() {
  const t = useStrings('violationList')
  const titleId = useId()

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-4 rounded-md border border-border p-4 sm:p-6"
    >
      <div className="flex items-center gap-3">
        <CheckCircleIcon className="shrink-0 text-success" />
        <h2 id={titleId} className="text-section font-semibold">
          {format(t.found, { n: 0 })}
        </h2>
      </div>
      <p className="max-w-[72ch]">{t.cleanText}</p>
      <p className="max-w-[72ch] text-text-muted">{t.cleanHint}</p>
      <TextLink href="#/rules">{t.whatWeLookFor}</TextLink>
    </section>
  )
}

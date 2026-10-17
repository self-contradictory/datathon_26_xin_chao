import { useId } from 'react'
import type { Violation } from '@/api/types'
import { ChevronRightIcon } from '@/components/icons'
import { TimeChip } from './TimeChip'
import { useViolationText } from './violationText'
import { ViolationDetails } from './ViolationDetails'

export function ViolationList({
  violations,
  activeIndex,
  onSelect,
}: {
  violations: readonly Violation[]
  activeIndex: number
  onSelect: (index: number) => void
}) {
  const baseId = useId()
  const { typeName, typeLang } = useViolationText()

  return (
    <ul className="overflow-hidden rounded-md border border-border bg-bg shadow-card">
      {violations.map((violation, index) => {
        const active = index === activeIndex
        const detailsId = `${baseId}-${index}`
        return (
          <li key={index} className="border-b border-border last:border-b-0">
            <button
              type="button"
              aria-expanded={active}
              aria-controls={detailsId}
              onClick={() => onSelect(index)}
              className={`flex min-h-14 w-full cursor-pointer items-center gap-3 border-l-[3px] py-3 pr-4 pl-[13px] text-left transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
                active
                  ? 'border-brand bg-brand-tint'
                  : 'border-transparent bg-bg hover:bg-surface'
              }`}
            >
              <TimeChip seconds={violation.timecode_sec} onTint={active} />
              <span
                lang={typeLang(violation.type)}
                className={`min-w-0 flex-1 wrap-break-word ${active ? 'font-semibold' : ''}`}
              >
                {typeName(violation.type)}
              </span>
              <ChevronRightIcon
                size={20}
                className={`shrink-0 text-text-muted transition-transform duration-150 ${active ? 'rotate-90' : ''}`}
              />
            </button>
            {active && (
              <div id={detailsId} className="px-4 pt-4 pb-5 sm:px-6">
                <ViolationDetails key={index} violation={violation} />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

import { useId } from 'react'
import type { Violation } from '@/api/types'
import { CheckIcon, ChevronRightIcon } from '@/components/icons'
import type { Review, ReviewDecision } from '@/history/types'
import { TimeChip } from './TimeChip'
import { useViolationText } from './violationText'
import { ViolationDetails, type ClipSource } from './ViolationDetails'

export function ViolationList({
  violations,
  openIndex,
  playheadIndex,
  review,
  onSelect,
  onClose,
  onDecide,
  rowRef,
  clip,
}: {
  violations: readonly Violation[]
  openIndex: number | null
  playheadIndex: number | null
  review: Review
  onSelect: (index: number) => void
  onClose: () => void
  onDecide: (index: number, decision: ReviewDecision | null) => void
  rowRef: (index: number, row: HTMLLIElement | null) => void
  clip: ClipSource | null
}) {
  const baseId = useId()
  const { typeName, typeLang } = useViolationText()

  return (
    <ul className="overflow-hidden rounded-lg border border-border bg-bg shadow-card">
      {violations.map((violation, index) => {
        const active = index === openIndex
        const playing = index === playheadIndex
        const decision = review[index]?.decision ?? null
        const rejected = decision === 'rejected'
        const detailsId = `${baseId}-${index}`
        return (
          <li
            key={index}
            ref={(row) => rowRef(index, row)}
            className="scroll-mt-4 border-b border-border last:border-b-0"
          >
            <button
              type="button"
              aria-expanded={active}
              aria-controls={active ? detailsId : undefined}
              onClick={() => (active ? onClose() : onSelect(index))}
              className={`flex min-h-14 w-full cursor-pointer items-center gap-3 border-l-[3px] py-3 pr-4 pl-[13px] text-left transition-colors duration-150 ease-out focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
                playing ? 'border-brand' : 'border-transparent'
              } ${active ? 'bg-brand-tint' : 'bg-bg hover:bg-surface'}`}
            >
              <TimeChip seconds={violation.timecode_sec} onTint={active} />
              <span
                lang={typeLang(violation.type)}
                className={`min-w-0 flex-1 wrap-break-word ${active ? 'font-semibold' : ''} ${rejected ? 'text-text-muted line-through' : ''}`}
              >
                {typeName(violation.type)}
              </span>
              {decision === 'confirmed' && (
                <CheckIcon size={20} className="shrink-0 text-danger" />
              )}
              <ChevronRightIcon
                size={20}
                className={`shrink-0 text-text-muted transition-transform duration-150 ${active ? 'rotate-90' : ''}`}
              />
            </button>
            {active && (
              <div id={detailsId} className="px-4 pt-4 pb-5 sm:px-6">
                <ViolationDetails
                  violation={violation}
                  decision={decision}
                  onDecide={(next) => onDecide(index, next)}
                  clip={clip}
                />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

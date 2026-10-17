import { useId, type ReactNode } from 'react'
import type { Violation } from '@/api/types'
import { ChevronLeftIcon, ChevronRightIcon } from '@/components/icons'
import { RuleNorm } from '@/components/RuleNorm'
import { TextLink } from '@/components/TextLink'
import { format, useStrings } from '@/i18n'
import { findRule } from '@/rules'
import { EvidenceFrames } from './EvidenceFrames'
import { IconButton } from './IconButton'
import { TimeChip } from './TimeChip'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-border py-4 last:pb-0">
      <dt className="shrink-0 grow-0 basis-[200px] font-semibold text-text-muted">
        {label}
      </dt>
      <dd className="max-w-[72ch] min-w-0 flex-[1_1_320px] wrap-break-word">
        {children}
      </dd>
    </div>
  )
}

function RuleCitation({ type }: { type: string }) {
  const t = useStrings('violationCard')
  const rule = findRule(type)
  if (!rule) return <span className="text-text-muted">{t.ruleUnknown}</span>

  return (
    <div className="flex flex-col gap-1">
      <span>
        <RuleNorm rule={rule} />
      </span>
      {rule.url && (
        <TextLink href={rule.url} external>
          {t.adilet}
        </TextLink>
      )}
    </div>
  )
}

export function ViolationCard({
  violation,
  index,
  total,
  onStep,
}: {
  violation: Violation
  index: number
  total: number
  onStep: (by: -1 | 1) => void
}) {
  const t = useStrings('violationCard')
  const titleId = useId()

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-6 rounded-md border border-border p-4 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-secondary text-text-muted">
            {format(t.position, { i: index + 1, n: total })}
          </span>
          <h2
            id={titleId}
            lang="ru"
            className="text-section font-semibold wrap-break-word"
          >
            {violation.type}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <TimeChip seconds={violation.timecode_sec} />
          {total > 1 && (
            <>
              <IconButton label={t.prev} onClick={() => onStep(-1)}>
                <ChevronLeftIcon size={20} />
              </IconButton>
              <IconButton label={t.next} onClick={() => onStep(1)}>
                <ChevronRightIcon size={20} />
              </IconButton>
            </>
          )}
        </div>
      </div>

      <EvidenceFrames
        key={index}
        frames={violation.evidence_frames}
        type={violation.type}
      />

      <dl className="flex flex-col">
        <Row label={t.description}>
          <span lang="ru">{violation.description}</span>
        </Row>
        <Row label={t.rule}>
          <RuleCitation type={violation.type} />
        </Row>
      </dl>
    </section>
  )
}

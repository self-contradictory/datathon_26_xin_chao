import type { ReactNode } from 'react'
import type { Violation } from '@/api/types'
import { RuleNorm } from '@/components/RuleNorm'
import { TextLink } from '@/components/TextLink'
import { Button } from '@/components/Button'
import { CheckIcon, CloseIcon } from '@/components/icons'
import type { ReviewDecision } from '@/history/types'
import { format, useStrings } from '@/i18n'
import { findRule, ruleHref } from '@/rules'
import { EvidenceFrames } from './EvidenceFrames'
import { useViolationText } from './violationText'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-border py-4 last:pb-0">
      <dt className="shrink-0 grow-0 basis-[160px] font-semibold text-text-muted">
        {label}
      </dt>
      <dd className="max-w-[72ch] min-w-0 flex-[1_1_280px] wrap-break-word">
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
      <a
        href={ruleHref(type) ?? undefined}
        className="w-fit rounded-sm text-text no-underline transition-colors duration-150 ease-out hover:text-brand hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <RuleNorm rule={rule} />
      </a>
      {rule.url && (
        <TextLink href={rule.url} external>
          {t.adilet}
        </TextLink>
      )}
    </div>
  )
}

function ReviewControls({
  decision,
  onDecide,
}: {
  decision: ReviewDecision | null
  onDecide: (decision: ReviewDecision | null) => void
}) {
  const t = useStrings('review')

  if (!decision) {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          icon={<CheckIcon size={20} />}
          onClick={() => onDecide('confirmed')}
          className="h-9 px-4"
        >
          {t.confirm}
        </Button>
        <Button
          variant="secondary"
          icon={<CloseIcon size={20} />}
          onClick={() => onDecide('rejected')}
          className="h-9 px-4"
        >
          {t.reject}
        </Button>
      </div>
    )
  }

  const confirmed = decision === 'confirmed'
  const label = confirmed ? t.confirmed : t.rejected
  return (
    <button
      type="button"
      aria-label={format(t.undo, { decision: label })}
      title={format(t.undo, { decision: label })}
      onClick={() => onDecide(null)}
      className={`inline-flex h-9 w-fit cursor-pointer items-center gap-2 rounded-full px-4 text-secondary font-semibold transition-colors duration-150 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
        confirmed
          ? 'bg-danger-tint text-danger-text hover:bg-danger-tint/70'
          : 'bg-surface text-text-muted hover:bg-border'
      }`}
    >
      {confirmed ? <CheckIcon size={20} /> : <CloseIcon size={20} />}
      {label}
    </button>
  )
}

export function ViolationDetails({
  violation,
  decision,
  onDecide,
}: {
  violation: Violation
  decision: ReviewDecision | null
  onDecide: (decision: ReviewDecision | null) => void
}) {
  const t = useStrings('violationCard')
  const { typeName, description, descriptionLang } = useViolationText()

  return (
    <div className="flex flex-col gap-4">
      <EvidenceFrames
        frames={violation.evidence_frames}
        type={typeName(violation.type)}
      />
      <dl className="flex flex-col">
        <Row label={t.description}>
          <span lang={descriptionLang(violation)}>
            {description(violation)}
          </span>
        </Row>
        <Row label={t.rule}>
          <RuleCitation type={violation.type} />
        </Row>
      </dl>
      <ReviewControls decision={decision} onDecide={onDecide} />
    </div>
  )
}

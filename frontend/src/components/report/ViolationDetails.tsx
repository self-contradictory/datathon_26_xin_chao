import type { ReactNode } from 'react'
import type { Violation } from '@/api/types'
import { RuleNorm } from '@/components/RuleNorm'
import { TextLink } from '@/components/TextLink'
import { Button } from '@/components/Button'
import { CheckIcon, CloseIcon } from '@/components/icons'
import type { ReviewDecision } from '@/history/types'
import { format, useStrings } from '@/i18n'
import { ACT_URLS, findRule, ruleActs, type Rule } from '@/rules'
import { ClipButton } from '@/components/clip/ClipButton'
import { EvidenceFrames } from './EvidenceFrames'
import { useViolationText } from './violationText'

export interface ClipSource {
  videoUrl: string
  fileName: string
}

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

function AdiletLinks({ rule }: { rule: Rule }) {
  const t = useStrings('violationCard')
  const rules = useStrings('rules')
  const acts = useStrings('acts')
  return (
    <ul className="flex flex-col">
      {ruleActs(rule).map((act) => (
        <li key={act}>
          <TextLink
            href={ACT_URLS[act]}
            label={format(rules.linkLabel, { act: acts[act] })}
          >
            {format(t.adilet, { act: acts[act] })}
          </TextLink>
        </li>
      ))}
    </ul>
  )
}

function RuleCitation({ rule }: { rule: Rule }) {
  const applicability = useStrings('applicability')
  return (
    <div className="flex flex-col items-start gap-2">
      <a
        href={`#/rules/${rule.id}`}
        className="inline-flex min-h-11 w-fit items-center rounded-sm text-text underline decoration-border underline-offset-4 transition-colors hover:text-brand hover:decoration-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <RuleNorm rule={rule} />
      </a>
      <span className="rounded-full bg-surface px-3 py-1 text-secondary font-semibold">
        {applicability[rule.applicability]}
      </span>
      <AdiletLinks rule={rule} />
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
          data-review="confirm"
          onClick={() => onDecide('confirmed')}
        >
          {t.confirm}
        </Button>
        <Button
          variant="secondary"
          icon={<CloseIcon size={20} />}
          onClick={() => onDecide('rejected')}
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
      className={`inline-flex h-11 w-fit cursor-pointer items-center gap-2 rounded-full px-4 text-secondary font-semibold transition-colors duration-150 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
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
  clip,
}: {
  violation: Violation
  decision: ReviewDecision | null
  onDecide: (decision: ReviewDecision | null) => void
  clip: ClipSource | null
}) {
  const t = useStrings('violationCard')
  const requires = useStrings('ruleRequires')
  const check = useStrings('ruleCheck')
  const { typeName } = useViolationText()
  const rule = findRule(violation.type)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <EvidenceFrames
            frames={violation.evidence_frames}
            type={typeName(violation.type)}
          />
        </div>
        {clip && (
          <ClipButton
            violation={violation}
            videoUrl={clip.videoUrl}
            fileName={clip.fileName}
          />
        )}
      </div>
      <dl className="flex flex-col">
        <Row label={t.description}>
          <span lang="ru">{violation.description}</span>
        </Row>
        {rule ? (
          <>
            <Row label={t.requires}>{requires[rule.id]}</Row>
            <Row label={t.check}>{check[rule.id]}</Row>
            <Row label={t.rule}>
              <RuleCitation rule={rule} />
            </Row>
          </>
        ) : (
          <Row label={t.rule}>{t.ruleUnknown}</Row>
        )}
      </dl>
      <ReviewControls decision={decision} onDecide={onDecide} />
    </div>
  )
}

import type { ReactNode } from 'react'
import type { Violation } from '@/api/types'
import { RuleNorm } from '@/components/RuleNorm'
import { TextLink } from '@/components/TextLink'
import { useStrings } from '@/i18n'
import { findRule } from '@/rules'
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

export function ViolationDetails({ violation }: { violation: Violation }) {
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
    </div>
  )
}

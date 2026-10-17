import { format, useStrings } from '@/i18n'
import type { Rule } from '@/rules'

export function RuleNorm({ rule }: { rule: Rule }) {
  const t = useStrings('ruleNorm')
  const document = rule.document.replace(/№ /g, '№ ')
  return (
    <>
      {rule.clause
        ? format(t.clause, { document, clause: rule.clause })
        : format(t.clausePending, { document })}
    </>
  )
}

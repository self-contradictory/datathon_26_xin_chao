import { format, useStrings } from '@/i18n'
import type { Norm, Ref, Rule } from '@/rules'

export function useNormText() {
  const t = useStrings('ruleNorm')
  const acts = useStrings('acts')

  function refText(ref: Ref): string {
    if ('article' in ref)
      return format(t.article, { a: ref.article, p: ref.point })
    if (!ref.subs?.length) return format(t.point, { p: ref.point })
    const s = ref.subs
      .map((sub) => format(t.subItem, { s: sub }))
      .join(t.subJoin)
    return format(t.sub, { p: ref.point, s })
  }

  function normText(norm: Norm): string {
    if (!norm.refs.length) return acts[norm.act]
    return format(t.norm, {
      act: acts[norm.act],
      refs: norm.refs.map(refText).join(', '),
    })
  }

  return (rule: Rule) => rule.norms.map(normText).join('; ')
}

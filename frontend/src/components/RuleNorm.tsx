import type { Rule } from '@/rules'
import { useNormText } from './normText'

export function RuleNorm({ rule }: { rule: Rule }) {
  const normText = useNormText()
  return <>{normText(rule)}</>
}

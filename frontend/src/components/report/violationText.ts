import { useStrings } from '@/i18n'
import { findRule } from '@/rules'

export function useViolationText() {
  const t = useStrings('violationTypes')

  function typeName(type: string): string {
    const rule = findRule(type)
    return rule ? t[rule.id] : type
  }

  function typeLang(type: string): 'ru' | undefined {
    return findRule(type) ? undefined : 'ru'
  }

  return { typeName, typeLang }
}

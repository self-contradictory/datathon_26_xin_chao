import { FIXTURE_TYPE } from '@/api/fixtureSource'
import type { Violation } from '@/api/types'
import { format, useStrings } from '@/i18n'
import { findRule } from '@/rules'

export function useViolationText() {
  const t = useStrings('violationTypes')

  function typeName(type: string): string {
    const rule = findRule(type)
    if (rule) return t[rule.id]
    return type === FIXTURE_TYPE ? t.fixture : type
  }

  function typeLang(type: string): 'ru' | undefined {
    return findRule(type) || type === FIXTURE_TYPE ? undefined : 'ru'
  }

  function description(violation: Violation): string {
    if (violation.type !== FIXTURE_TYPE) return violation.description
    return format(t.fixtureDescription, {
      second: Math.round(violation.timecode_sec),
    })
  }

  function descriptionLang(violation: Violation): 'ru' | undefined {
    return violation.type === FIXTURE_TYPE ? undefined : 'ru'
  }

  return { typeName, typeLang, description, descriptionLang }
}

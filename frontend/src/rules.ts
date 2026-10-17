import type { Messages } from '@/i18n'

export type RuleId = keyof Messages['ruleLooks']

export interface Rule {
  id: RuleId
  type: string
  document: string
  clause: string | null
  url: string | null
}

export const RULES: readonly Rule[] = [
  {
    id: 'cashOutOfView',
    type: 'Наличные вне зоны видимости камеры',
    document: 'Постановление НБРК № 231',
    clause: null,
    url: null,
  },
  {
    id: 'outsider',
    type: 'Посторонний в кассовой зоне',
    document: 'Постановление НБРК № 231',
    clause: null,
    url: null,
  },
  {
    id: 'unattended',
    type: 'Касса без присмотра',
    document: 'Постановление НБРК № 231',
    clause: null,
    url: null,
  },
  {
    id: 'countHidden',
    type: 'Пересчёт не на виду у клиента',
    document: 'Постановление НБРК № 231',
    clause: null,
    url: null,
  },
  {
    id: 'personalItems',
    type: 'Наличные в личных вещах',
    document: 'Постановление НБРК № 231',
    clause: null,
    url: null,
  },
  {
    id: 'phone',
    type: 'Телефон в руках при работе с наличными',
    document: 'Постановление НБРК № 231',
    clause: null,
    url: null,
  },
]

function normalize(type: string): string {
  return type.trim().toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ')
}

export function findRule(type: string): Rule | null {
  const key = normalize(type)
  return RULES.find((rule) => normalize(rule.type) === key) ?? null
}

export function ruleHref(type: string): string | null {
  const rule = findRule(type)
  return rule ? `#/rules/${rule.id}` : null
}

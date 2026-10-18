import type { Messages } from '@/i18n'

export type RuleId = keyof Messages['ruleRequires']
export type ActId = keyof Messages['acts']
export type Applicability = keyof Messages['applicability']

export type Ref =
  | { point: string; subs?: readonly string[] }
  | { article: string; point: string }

export interface Norm {
  act: ActId
  refs: readonly Ref[]
}

export interface Rule {
  id: RuleId
  type: string
  norms: readonly Norm[]
  applicability: Applicability
}

export const ACT_URLS: Record<ActId, string> = {
  nbrk231: 'https://adilet.zan.kz/rus/docs/V1900019680',
  nbrk14: 'https://adilet.zan.kz/rus/docs/V2000020075',
  nbrk230: 'https://adilet.zan.kz/rus/docs/V1700016120',
  ardfm53: 'https://adilet.zan.kz/rus/docs/V2600038336',
  aml: 'https://adilet.zan.kz/rus/docs/Z090000191_',
}

export const RULES: readonly Rule[] = [
  {
    id: 'cashLeftOut',
    type: 'Принятые деньги не убраны в запираемое место',
    norms: [{ act: 'nbrk231', refs: [{ point: '20' }] }],
    applicability: 'direct',
  },
  {
    id: 'countWithoutClient',
    type: 'Пересчёт без клиента',
    norms: [
      {
        act: 'nbrk231',
        refs: [{ point: '20' }, { point: '31', subs: ['4'] }],
      },
    ],
    applicability: 'direct',
  },
  {
    id: 'mixedCash',
    type: 'Деньги разных клиентов смешаны',
    norms: [
      {
        act: 'nbrk231',
        refs: [
          { point: '19', subs: ['2', '4'] },
          { point: '20' },
          { point: '21' },
        ],
      },
    ],
    applicability: 'direct',
  },
  {
    id: 'noRecount',
    type: 'Деньги приняты без пересчёта и учёта',
    norms: [
      {
        act: 'nbrk231',
        refs: [
          { point: '19', subs: ['2', '4'] },
          { point: '20' },
          { point: '31', subs: ['4'] },
        ],
      },
    ],
    applicability: 'direct',
  },
  {
    id: 'partialReturn',
    type: 'Часть принятых денег возвращена клиенту',
    norms: [
      {
        act: 'nbrk231',
        refs: [{ point: '19', subs: ['2', '4'] }, { point: '20' }],
      },
    ],
    applicability: 'verify',
  },
  {
    id: 'rejectedNotes',
    type: 'Отклонённые банкноты смешаны с принятыми',
    norms: [
      {
        act: 'nbrk231',
        refs: [{ point: '19', subs: ['2'] }, { point: '57' }, { point: '59' }],
      },
      { act: 'nbrk230', refs: [] },
    ],
    applicability: 'verify',
  },
  {
    id: 'noId',
    type: 'Клиент обслужен без удостоверения личности',
    norms: [
      {
        act: 'nbrk231',
        refs: [
          { point: '19', subs: ['1'] },
          { point: '31', subs: ['1'] },
          { point: '7' },
        ],
      },
      { act: 'aml', refs: [{ article: '5', point: '1' }] },
    ],
    applicability: 'conditional',
  },
  {
    id: 'safeOpen',
    type: 'Сейф оставлен открытым',
    norms: [
      {
        act: 'nbrk231',
        refs: [{ point: '20' }, { point: '80' }],
      },
    ],
    applicability: 'direct',
  },
  {
    id: 'keyLeft',
    type: 'Ключ оставлен в сейфе',
    norms: [{ act: 'nbrk231', refs: [{ point: '80' }] }],
    applicability: 'internal',
  },
  {
    id: 'stampsLeft',
    type: 'Печати и штампы оставлены на столе',
    norms: [{ act: 'nbrk231', refs: [{ point: '80' }] }],
    applicability: 'internal',
  },
  {
    id: 'personalItems',
    type: 'Личные вещи в кассовом узле',
    norms: [{ act: 'nbrk231', refs: [{ point: '12' }] }],
    applicability: 'direct',
  },
  {
    id: 'sessionUnlocked',
    type: 'Компьютер оставлен без блокировки',
    norms: [
      {
        act: 'ardfm53',
        refs: [{ point: '71', subs: ['9'] }],
      },
    ],
    applicability: 'indirect',
  },
  {
    id: 'doorOpen',
    type: 'Служебная дверь кассы открыта',
    norms: [
      { act: 'nbrk14', refs: [{ point: '16', subs: ['1'] }, { point: '8' }] },
    ],
    applicability: 'indirect',
  },
  {
    id: 'notReady',
    type: 'Обслуживание до включения оборудования',
    norms: [
      { act: 'nbrk231', refs: [{ point: '9' }] },
      { act: 'nbrk14', refs: [{ point: '16', subs: ['6'] }] },
    ],
    applicability: 'conditional',
  },
  {
    id: 'leftDuringService',
    type: 'Кассир покинул рабочее место до окончания обслуживания клиента',
    norms: [{ act: 'nbrk231', refs: [{ point: '22' }] }],
    applicability: 'direct',
  },
]

function normalize(type: string): string {
  return type.trim().toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ')
}

export function findRule(type: string): Rule | null {
  const key = normalize(type)
  return (
    RULES.find(
      (rule) => normalize(rule.type) === key || rule.id.toLowerCase() === key,
    ) ?? null
  )
}

export function ruleActs(rule: Rule): ActId[] {
  return [...new Set(rule.norms.map((norm) => norm.act))]
}

import type { RuleId } from '@/rules'

interface LabelEntry {
  second: number
  rules: readonly RuleId[]
  finding: string
}

const LABELS: Record<string, LabelEntry | null> = {
  'X-1': {
    second: 22,
    rules: ['partialReturn'],
    finding:
      'Необоснованный возврат части наличных денег клиенту при проведении приходной кассовой операции',
  },
  'X-2': {
    second: 10,
    rules: ['noId'],
    finding:
      'Возможная идентификация клиента без документа или допустимых цифровых данных при кассовой операции',
  },
  'X-3': null,
  'X-4': {
    second: 57,
    rules: ['cashLeftOut'],
    finding:
      'Хранение ранее принятых наличных на открытом рабочем месте, а не в запираемом устройстве',
  },
  'X-5': null,
  'X-8': null,
  'X-10': null,
  'X-11': {
    second: 18,
    rules: ['sessionUnlocked'],
    finding:
      'Возможное оставление незаблокированного пользовательского сеанса на рабочем месте',
  },
  'X-12': null,
  'X-13': {
    second: 47,
    rules: ['noRecount'],
    finding:
      'Приём наличных без обязательного пересчёта и сверки и возможное отсутствие их учёта',
  },
  'X-14': null,
  'X-15': {
    second: 15,
    rules: ['cashLeftOut'],
    finding:
      'Незащищённое оставление сумки с ранее принятыми наличными на рабочем месте',
  },
  'X-16': null,
  'X-17': {
    second: 7,
    rules: ['noId'],
    finding:
      'Возможное обслуживание кассового клиента без надлежащей идентификации',
  },
  'X-18': {
    second: 20,
    rules: ['noId', 'cashLeftOut'],
    finding:
      'Возможное обслуживание без идентификации и одновременное открытое размещение наличных при смене клиентов',
  },
  'X-19': null,
  'X-20': {
    second: 5,
    rules: ['safeOpen'],
    finding:
      'Оставление открытого устройства хранения наличных без обеспечения сохранности',
  },
  'X-21': null,
  'X-22': {
    second: 14,
    rules: ['keyLeft'],
    finding:
      'Возможное ненадлежащее хранение ключа от сейфа и риск несанкционированного доступа',
  },
  'X-23': null,
  'X-24': {
    second: 8,
    rules: ['stampsLeft'],
    finding:
      'Оставление именных штампов, печатей и иных средств удостоверения без защиты от несанкционированного использования',
  },
  'X-25': null,
  'X-26': {
    second: 9,
    rules: ['cashLeftOut'],
    finding:
      'Несоблюдение порядка хранения ранее принятых наличных в защищённом месте',
  },
  'X-27': null,
  'X-28': {
    second: 7,
    rules: ['sessionUnlocked'],
    finding:
      'Возможное оставление активной пользовательской сессии при отсутствии кассира',
  },
  'X-29': null,
  'X-30': {
    second: 13,
    rules: ['notReady'],
    finding:
      'Начало обслуживания до готовности необходимых средств контроля кассовых операций или безопасности',
  },
  'X-31': null,
  'X-32': {
    second: 5,
    rules: ['doorOpen'],
    finding: 'Оставление служебной двери кассового помещения открытой',
  },
  'X-33': {
    second: 6,
    rules: ['doorOpen'],
    finding:
      'Оставление служебной двери кассового помещения открытой, создающее риск несанкционированного доступа',
  },
  'X-34': {
    second: 13,
    rules: ['countWithoutClient'],
    finding: 'Продолжение пересчёта принимаемых денег в отсутствие клиента',
  },
  'X-35': null,
  'X-37': null,
  'X-38': {
    second: 33,
    rules: ['cashLeftOut', 'countWithoutClient'],
    finding:
      'Необеспечение хранения ранее принятых денег и возможный пересчёт без присутствия клиента',
  },
  'X-39': null,
  'X-40': {
    second: 17,
    rules: ['personalItems'],
    finding: 'Возможное хранение личных вещей работника внутри кассового узла',
  },
  'X-43': null,
  'X-44': {
    second: 16,
    rules: ['rejectedNotes'],
    finding:
      'Смешение банкнот, отклонённых счётно-сортировальным оборудованием, с принятыми',
  },
  'X-45': null,
  'X-46': {
    second: 11,
    rules: ['cashLeftOut'],
    finding:
      'Ранее принятые деньги не убраны в запираемое устройство при прерывании кассовой операции',
  },
  'X-47': {
    second: 68,
    rules: ['cashLeftOut', 'mixedCash'],
    finding:
      'Смешение сумм разных клиентов и незащищённое хранение ранее принятых наличных',
  },
  'X-48': null,
}

export function labelKey(fileName: string): string {
  const base = fileName.replace(/\.[^.]+$/, '').trim()
  return base.replace(/^[ХхXx]\s*-\s*0*(\d+)$/, (_, n: string) => `X-${n}`)
}

export type Label =
  ({ kind: 'violation' } & LabelEntry) | { kind: 'clean' } | { kind: 'unknown' }

export function lookupLabel(fileName: string): Label {
  const key = labelKey(fileName)
  if (!(key in LABELS)) return { kind: 'unknown' }
  const entry = LABELS[key]
  return entry ? { kind: 'violation', ...entry } : { kind: 'clean' }
}

export const LABEL_COUNT = Object.keys(LABELS).length

const LABELS: Record<string, number | null> = {
  'X-1': 22,
  'X-2': 10,
  'X-3': null,
  'X-4': 57,
  'X-5': null,
  'X-8': null,
  'X-10': null,
  'X-11': 18,
  'X-12': null,
  'X-13': 47,
  'X-14': null,
  'X-15': 15,
  'X-16': null,
  'X-17': 7,
  'X-18': 20,
  'X-19': null,
  'X-20': 5,
  'X-21': null,
  'X-22': 14,
  'X-23': null,
  'X-24': 8,
  'X-25': null,
  'X-26': 9,
  'X-27': null,
  'X-28': 7,
  'X-29': null,
  'X-30': 13,
  'X-31': null,
  'X-32': 5,
  'X-33': 6,
  'X-34': 13,
  'X-35': null,
  'X-37': null,
  'X-38': 33,
  'X-39': null,
  'X-40': 17,
  'X-43': null,
  'X-44': 16,
  'X-45': null,
  'X-46': 11,
  'X-47': 68,
  'X-48': null,
}

export function labelKey(fileName: string): string {
  const base = fileName.replace(/\.[^.]+$/, '').trim()
  return base.replace(/^[ХхXx]\s*-\s*0*(\d+)$/, (_, n: string) => `X-${n}`)
}

export type Label =
  | { kind: 'violation'; second: number }
  | { kind: 'clean' }
  | { kind: 'unknown' }

export function lookupLabel(fileName: string): Label {
  const key = labelKey(fileName)
  if (!(key in LABELS)) return { kind: 'unknown' }
  const second = LABELS[key]
  return second === null || second === undefined
    ? { kind: 'clean' }
    : { kind: 'violation', second }
}

export const LABEL_COUNT = Object.keys(LABELS).length

import type { RuleSource, Violation } from '@/api/types'
import { ACT_URLS, type ActId } from '@/rules'

const REVIEW_NOTE = ' The rule is still a candidate awaiting legal review.'
const SOURCE_ACTS: readonly [RegExp, ActId][] = [
  [/НБРК от 29\.11\.2019 №\s*231\b/, 'nbrk231'],
  [/НБРК от 24\.02\.2020 №\s*14\b/, 'nbrk14'],
  [/НБРК от 29\.11\.2017 №\s*230\b/, 'nbrk230'],
  [/АРРФР от 03\.04\.2026 №\s*53\b/, 'ardfm53'],
  [/28\.08\.2009 №\s*191-IV\b/, 'aml'],
]

export function safeSourceUrl(url: string | null): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
      ? parsed.href
      : null
  } catch {
    return null
  }
}

export function violationDetails(violation: Violation): {
  description: string
  source: RuleSource | null
} {
  const marker = violation.description.lastIndexOf(' Rule: ')
  if (marker < 0) {
    return {
      description: violation.description,
      source: violation.source ?? null,
    }
  }

  const text = violation.description.slice(marker + ' Rule: '.length)
  const reviewNote = text.endsWith(REVIEW_NOTE) ? REVIEW_NOTE : ''
  const citation = (reviewNote ? text.slice(0, -reviewNote.length) : text)
    .trim()
    .replace(/\.$/, '')
  if (!citation) {
    return {
      description: violation.description,
      source: violation.source ?? null,
    }
  }
  const parts = /^(.*?),\s*((?:п\.|ст\.|§)[\s\S]+)$/.exec(citation)
  const document = parts?.[1] ?? citation
  const act = SOURCE_ACTS.find(([pattern]) => pattern.test(document))?.[1]

  return {
    description: violation.description.slice(0, marker) + reviewNote,
    source: violation.source ?? {
      document,
      clause: parts?.[2] ?? null,
      url: act ? ACT_URLS[act] : null,
    },
  }
}

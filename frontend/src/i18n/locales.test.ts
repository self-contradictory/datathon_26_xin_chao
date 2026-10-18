import { describe, expect, test } from 'bun:test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  LOCALES_DIR,
  readLocale,
  renderRuTypes,
  TRANSLATION_TYPES,
} from '../../scripts/i18n-types'
import { messagesFor } from './index'

const ru = readLocale('ru')
const translations = { kk: readLocale('kk'), en: readLocale('en') }

const SAME_IN_EVERY_LANGUAGE = new Set([
  'header.api',
  'header.brand',
  'titles.api',
  'titles.suffix',
  'report.json',
  'languages.kk',
  'languages.ru',
  'languages.en',
])

const RUSSIAN_PLURAL_FORMS = new Set([
  'jsonView.charsFew',
  'jsonView.charsMany',
])

const placeholders = (text: string) =>
  [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()

describe('locales', () => {
  test('ru.yaml has only non-empty strings', () => {
    for (const [namespace, strings] of Object.entries(ru)) {
      for (const [key, value] of Object.entries(strings)) {
        expect(typeof value, `${namespace}.${key}`).toBe('string')
        expect(value.length, `${namespace}.${key}`).toBeGreaterThan(0)
      }
    }
  })

  for (const [lang, messages] of Object.entries(translations)) {
    test(`${lang}.yaml uses only keys that exist in ru.yaml`, () => {
      for (const [namespace, strings] of Object.entries(messages)) {
        expect(ru[namespace], `${lang}: ${namespace}`).toBeDefined()
        for (const key of Object.keys(strings)) {
          expect(
            ru[namespace]?.[key],
            `${lang}: ${namespace}.${key}`,
          ).toBeDefined()
        }
      }
    })

    test(`${lang}.yaml translates every key of ru.yaml`, () => {
      const missing: string[] = []
      for (const [namespace, strings] of Object.entries(ru)) {
        for (const key of Object.keys(strings)) {
          const path = `${namespace}.${key}`
          if (SAME_IN_EVERY_LANGUAGE.has(path)) continue
          if (RUSSIAN_PLURAL_FORMS.has(path)) continue
          if (messages[namespace]?.[key] === undefined) missing.push(path)
        }
      }
      expect(missing).toEqual([])
    })

    test(`${lang}.yaml keeps the same {placeholders} as ru.yaml`, () => {
      for (const [namespace, strings] of Object.entries(messages)) {
        for (const [key, value] of Object.entries(strings)) {
          expect(placeholders(value), `${lang}: ${namespace}.${key}`).toEqual(
            placeholders(ru[namespace]![key]!),
          )
        }
      }
    })
  }

  test('generated types match ru.yaml (run bun run i18n:types)', () => {
    const read = (name: string) => readFileSync(join(LOCALES_DIR, name), 'utf8')
    expect(read('ru.d.yaml.ts')).toBe(renderRuTypes(ru))
    expect(read('kk.d.yaml.ts')).toBe(TRANSLATION_TYPES)
    expect(read('en.d.yaml.ts')).toBe(TRANSLATION_TYPES)
  })

  test('a missing translation falls back to Russian', () => {
    expect(messagesFor('header', 'en').api).toBe(ru.header!.api!)
    expect(messagesFor('header', 'en').rules).toBe('Rules')
  })
})

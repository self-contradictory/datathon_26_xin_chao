import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

export const LOCALES_DIR = join(import.meta.dir, '..', 'src', 'i18n', 'locales')

type Messages = Record<string, Record<string, string>>

const quote = (key: string) =>
  /^[A-Za-z_$][\w$]*$/.test(key) ? key : JSON.stringify(key)

export function renderRuTypes(messages: Messages): string {
  const namespaces = Object.entries(messages).map(([namespace, strings]) => {
    const keys = Object.keys(strings)
      .map((key) => `    ${quote(key)}: string`)
      .join('\n')
    return `  ${quote(namespace)}: {\n${keys}\n  }`
  })
  return [
    'export interface Messages {',
    ...namespaces,
    '}',
    '',
    'declare const messages: Messages',
    'export default messages',
    '',
  ].join('\n')
}

export const TRANSLATION_TYPES = [
  "import type { Messages } from './ru.yaml'",
  '',
  'declare const messages: {',
  '  [Namespace in keyof Messages]?: Partial<Messages[Namespace]>',
  '}',
  'export default messages',
  '',
].join('\n')

export function readLocale(lang: string): Messages {
  return Bun.YAML.parse(
    readFileSync(join(LOCALES_DIR, `${lang}.yaml`), 'utf8'),
  ) as Messages
}

if (import.meta.main) {
  writeFileSync(
    join(LOCALES_DIR, 'ru.d.yaml.ts'),
    renderRuTypes(readLocale('ru')),
  )
  for (const lang of ['kk', 'en']) {
    writeFileSync(join(LOCALES_DIR, `${lang}.d.yaml.ts`), TRANSLATION_TYPES)
  }
  console.log('Wrote src/i18n/locales/*.d.yaml.ts')
}

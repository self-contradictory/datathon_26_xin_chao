import { createContext, useContext, useMemo } from 'react'
import en from './locales/en.yaml'
import kk from './locales/kk.yaml'
import ru, { type Messages } from './locales/ru.yaml'

export type Lang = 'kk' | 'ru' | 'en'
export const LANGS: readonly Lang[] = ['kk', 'ru', 'en']

export type { Messages }
export type Namespace = keyof Messages

const TRANSLATIONS = { kk, en }

export const LangContext = createContext<{
  lang: Lang
  setLang: (lang: Lang) => void
}>({
  lang: 'ru',
  setLang: () => {},
})

export function useLang() {
  return useContext(LangContext)
}

export function messagesFor<N extends Namespace>(
  namespace: N,
  lang: Lang,
): Messages[N] {
  if (lang === 'ru') return ru[namespace]
  return { ...ru[namespace], ...TRANSLATIONS[lang][namespace] }
}

export function useStrings<N extends Namespace>(namespace: N): Messages[N] {
  const { lang } = useLang()
  return useMemo(() => messagesFor(namespace, lang), [namespace, lang])
}

export function format(
  template: string,
  values: Record<string, string | number>,
): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  )
}

export function localeOf(lang: Lang): string {
  return lang === 'kk' ? 'kk-KZ' : lang === 'en' ? 'en-GB' : 'ru-RU'
}

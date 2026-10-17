import { useEffect, useState, type ReactNode } from 'react'
import { LangContext, type Lang } from './index'

const STORAGE_KEY = 'forte-cash-check.lang'

function readStoredLang(): Lang {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'kk' || value === 'en' || value === 'ru' ? value : 'ru'
  } catch {
    return 'ru'
  }
}

export function LangProvider({
  children,
  initial,
}: {
  children: ReactNode
  initial?: Lang
}) {
  const [lang, setLang] = useState<Lang>(() => initial ?? readStoredLang())

  useEffect(() => {
    document.documentElement.lang = lang
    try {
      localStorage.setItem(STORAGE_KEY, lang)
    } catch {}
  }, [lang])

  return (
    <LangContext.Provider value={{ lang, setLang }}>
      {children}
    </LangContext.Provider>
  )
}

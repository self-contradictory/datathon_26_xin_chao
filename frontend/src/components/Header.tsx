import { useEffect, useRef, useState } from 'react'
import { USE_FIXTURES } from '@/config'
import { LANGS, useLang, useStrings } from '@/i18n'
import { CloseIcon, MenuIcon } from './icons'
import { Owl } from './Owl'

export type Route = 'main' | 'rules' | 'api' | 'history'

const FOCUS = 'focus-visible:outline-2 focus-visible:outline-brand'

function LangSwitch({ compact }: { compact: boolean }) {
  const { lang, setLang } = useLang()
  const languages = useStrings('languages')
  const t = useStrings('header')
  return (
    <div
      role="group"
      aria-label={t.language}
      className="inline-flex shrink-0 gap-1 rounded-full bg-surface p-1"
    >
      {LANGS.map((code) => {
        const active = code === lang
        return (
          <button
            key={code}
            type="button"
            lang={code}
            aria-pressed={active}
            onClick={() => setLang(code)}
            className={`h-10 cursor-pointer rounded-full text-secondary transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              compact ? 'min-w-10 px-2' : 'min-w-12 px-3'
            } ${active ? 'bg-bg font-semibold text-text shadow-popover' : 'text-text-muted hover:text-text'}`}
          >
            {languages[code]}
          </button>
        )
      })}
    </div>
  )
}

function HomeLink({ onHome }: { onHome: () => void }) {
  const t = useStrings('header')
  return (
    <a
      href="#/"
      aria-label={t.home}
      onClick={onHome}
      className={`mr-auto flex min-h-11 items-center gap-3 rounded-md text-brand-deep no-underline ${FOCUS}`}
    >
      <Owl mood="hello" className="w-11 shrink-0" />
      <span
        aria-hidden="true"
        className="text-[21px] leading-none font-bold tracking-[-0.02em] text-brand-deep sm:text-[24px]"
      >
        {t.brand}
      </span>
      {USE_FIXTURES && (
        <span className="rounded-full bg-brand-tint px-3 py-1 text-caption font-semibold text-brand max-sm:hidden">
          {t.demo}
        </span>
      )}
    </a>
  )
}

function NavLinks({
  route,
  inMenu,
  onNavigate,
}: {
  route: Route
  inMenu: boolean
  onNavigate?: () => void
}) {
  const t = useStrings('header')
  const links = [
    { href: '#/history', label: t.history, current: route === 'history' },
    { href: '#/rules', label: t.rules, current: route === 'rules' },
    { href: '#/api', label: t.api, current: route === 'api' },
  ]
  const shape = inMenu
    ? 'flex min-h-[52px] items-center border-b border-border px-2 last:border-b-0'
    : 'inline-flex h-11 items-center rounded-md px-4'

  return links.map((link) => (
    <a
      key={link.href}
      href={link.href}
      aria-current={link.current ? 'page' : undefined}
      onClick={onNavigate}
      className={`${shape} no-underline transition-colors duration-150 hover:bg-surface ${FOCUS} ${
        link.current ? 'bg-surface font-semibold text-text' : 'text-text'
      }`}
    >
      {link.label}
    </a>
  ))
}

function MobileMenu({ route }: { route: Route }) {
  const t = useStrings('header')
  const [openOn, setOpenOn] = useState<Route | null>(null)
  const open = openOn === route
  const close = () => setOpenOn(null)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const areaRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpenOn(null)
      toggleRef.current?.focus()
    }
    const onPointerDown = (event: PointerEvent) => {
      if (!areaRef.current?.contains(event.target as Node)) setOpenOn(null)
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [open])

  return (
    <div ref={areaRef} className="contents">
      <button
        ref={toggleRef}
        type="button"
        aria-label={open ? t.closeMenu : t.openMenu}
        title={open ? t.closeMenu : t.openMenu}
        aria-expanded={open}
        aria-controls={open ? 'mobile-menu' : undefined}
        onClick={() => setOpenOn(open ? null : route)}
        className={`flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full bg-surface text-text ${FOCUS}`}
      >
        {open ? <CloseIcon /> : <MenuIcon />}
      </button>
      {open && (
        <nav
          id="mobile-menu"
          aria-label={t.nav}
          className="absolute inset-x-0 top-16 z-20 flex flex-col border-b border-border bg-bg px-4 py-2 shadow-popover"
        >
          <NavLinks route={route} inMenu onNavigate={close} />
        </nav>
      )}
    </div>
  )
}

export function Header({
  route,
  onHome,
}: {
  route: Route
  onHome: () => void
}) {
  const t = useStrings('header')

  return (
    <header className="relative border-b border-border bg-canvas">
      <div className="hidden min-h-16 flex-wrap items-center gap-x-6 gap-y-2 px-6 py-2 sm:flex">
        <HomeLink onHome={onHome} />
        <nav aria-label={t.nav} className="flex flex-wrap items-center gap-2">
          <NavLinks route={route} inMenu={false} />
          <div className="ml-2">
            <LangSwitch compact={false} />
          </div>
        </nav>
      </div>

      <div className="flex h-16 items-center gap-2 px-4 sm:hidden">
        <HomeLink onHome={onHome} />
        <LangSwitch compact />
        <MobileMenu route={route} />
      </div>
    </header>
  )
}

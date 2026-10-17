import { useEffect, useRef, useState } from 'react'
import { LANGS, useLang, useStrings } from '@/i18n'
import { CloseIcon, MenuIcon } from './icons'
import { Owl } from './Owl'

export type Route = 'main' | 'rules' | 'api'

const FOCUS = 'focus-visible:outline-2 focus-visible:outline-brand'

function LangSwitch({ compact }: { compact: boolean }) {
  const { lang, setLang } = useLang()
  const languages = useStrings('languages')
  const t = useStrings('header')
  return (
    <div
      role="group"
      aria-label={t.language}
      className="flex overflow-hidden rounded-full border border-border"
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
            className={`h-[42px] cursor-pointer text-secondary transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
              compact ? 'min-w-11 px-2' : 'min-w-[52px] px-3'
            } ${active ? 'bg-brand-tint font-semibold text-brand' : 'bg-bg text-text hover:bg-surface'}`}
          >
            {languages[code]}
          </button>
        )
      })}
    </div>
  )
}

function HomeLink() {
  const t = useStrings('header')
  return (
    <a
      href="#/"
      aria-label={t.home}
      className={`mr-auto flex min-h-11 items-center gap-3 rounded-md text-brand-deep no-underline ${FOCUS}`}
    >
      <Owl mood="idle" className="w-10 shrink-0" />
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
        aria-expanded={open}
        aria-controls="mobile-menu"
        onClick={() => setOpenOn(open ? null : route)}
        className={`flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-md bg-surface text-text ${FOCUS}`}
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

export function Header({ route }: { route: Route }) {
  const t = useStrings('header')

  return (
    <header className="relative border-b border-border bg-canvas">
      <div className="hidden min-h-16 flex-wrap items-center gap-x-6 gap-y-2 px-6 py-2 sm:flex">
        <HomeLink />
        <nav aria-label={t.nav} className="flex flex-wrap items-center gap-2">
          <NavLinks route={route} inMenu={false} />
          <div className="ml-2">
            <LangSwitch compact={false} />
          </div>
        </nav>
      </div>

      <div className="flex h-16 items-center gap-2 px-4 sm:hidden">
        <HomeLink />
        <LangSwitch compact />
        <MobileMenu route={route} />
      </div>
    </header>
  )
}

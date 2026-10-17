import type { ReactNode } from 'react'
import { useStrings } from '@/i18n'
import { ExternalIcon } from './icons'

export function TextLink({
  href,
  external = false,
  label,
  children,
}: {
  href: string
  external?: boolean
  label?: string
  children: ReactNode
}) {
  const t = useStrings('textLink')
  return (
    <a
      href={href}
      aria-label={label}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      className="-my-2.5 inline-flex min-h-11 w-fit items-center gap-1 rounded-sm font-semibold text-brand underline underline-offset-2 hover:text-brand-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      {children}
      {external && (
        <>
          <ExternalIcon size={20} />
          {!label && <span className="sr-only">{t.newTab}</span>}
        </>
      )}
    </a>
  )
}

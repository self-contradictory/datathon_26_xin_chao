import type { ReactNode } from 'react'
import { ExternalIcon } from './icons'

export function TextLink({
  href,
  label,
  children,
}: {
  href: string
  label: string
  children: ReactNode
}) {
  return (
    <a
      href={href}
      aria-label={label}
      target="_blank"
      rel="noopener noreferrer"
      className="-my-2.5 inline-flex min-h-11 w-fit items-center gap-1 rounded-sm font-semibold text-brand underline underline-offset-2 hover:text-brand-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      {children}
      <ExternalIcon size={20} />
    </a>
  )
}

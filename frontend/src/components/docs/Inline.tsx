import type { ReactNode } from 'react'

export function Code({
  children,
  pill = false,
}: {
  children: ReactNode
  pill?: boolean
}) {
  return (
    <code
      translate="no"
      className={`font-mono text-secondary font-medium wrap-break-word ${
        pill ? 'rounded-sm bg-surface px-1.5 py-0.5' : ''
      }`}
    >
      {children}
    </code>
  )
}

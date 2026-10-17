import type { ComponentProps, ReactNode } from 'react'

export function IconButton({
  label,
  children,
  className = '',
  ...rest
}: Omit<ComponentProps<'button'>, 'aria-label' | 'title' | 'type'> & {
  label: string
  children: ReactNode
}) {
  return (
    <button
      {...rest}
      type="button"
      aria-label={label}
      title={label}
      className={`flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-border bg-bg text-text transition-colors hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-wait ${className}`}
    >
      {children}
    </button>
  )
}

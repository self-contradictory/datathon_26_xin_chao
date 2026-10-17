import type { ReactNode } from 'react'

export function DocSection({
  id,
  heading,
  divided = false,
  children,
}: {
  id: string
  heading: ReactNode
  divided?: boolean
  children: ReactNode
}) {
  return (
    <section
      aria-labelledby={id}
      className={`flex flex-col gap-4 ${divided ? 'border-t border-border pt-8' : ''}`}
    >
      <h2
        id={id}
        className="flex flex-wrap items-center gap-3 text-section font-semibold"
      >
        {heading}
      </h2>
      {children}
    </section>
  )
}

export function DocSubheading({ children }: { children: ReactNode }) {
  return <h3 className="mt-2 text-body font-semibold">{children}</h3>
}

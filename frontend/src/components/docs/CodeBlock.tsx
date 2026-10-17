import { useEffect, useId, useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { CopyIcon } from '@/components/icons'
import { useStrings } from '@/i18n'
import { copyText } from '@/utils/clipboard'

function useScrollsX<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [scrolls, setScrolls] = useState(false)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(() =>
      setScrolls(element.scrollWidth > element.clientWidth),
    )
    observer.observe(element)
    if (element.firstElementChild) observer.observe(element.firstElementChild)
    return () => observer.disconnect()
  }, [])
  return [ref, scrolls] as const
}

export function CodeBlock({
  label,
  context,
  code,
  notify,
}: {
  label: string
  context?: string
  code: string
  notify: (message: string) => void
}) {
  const t = useStrings('codeBlock')
  const labelId = useId()
  const name = context ? `${label} · ${context}` : label
  const [preRef, scrolls] = useScrollsX<HTMLPreElement>()

  async function copy() {
    notify((await copyText(code)) ? t.copied : t.copyFailed)
  }

  return (
    <figure aria-label={name} className="overflow-hidden rounded-md bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-border py-2 pr-2 pl-4">
        <span id={labelId} className="text-secondary text-text-muted">
          {label}
        </span>
        <Button
          variant="secondary"
          icon={<CopyIcon size={20} />}
          aria-describedby={labelId}
          onClick={() => void copy()}
        >
          {t.copy}
        </Button>
      </div>
      <pre
        ref={preRef}
        tabIndex={scrolls ? 0 : undefined}
        role={scrolls ? 'region' : undefined}
        aria-label={scrolls ? name : undefined}
        translate="no"
        className="overflow-x-auto p-4 font-mono text-secondary font-medium tabular-nums focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand"
      >
        <code className="block w-max">{code}</code>
      </pre>
    </figure>
  )
}

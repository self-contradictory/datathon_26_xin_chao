import { useRef, type KeyboardEvent } from 'react'
import { panelId, tabId } from './tabIds'
import { wrapIndex } from '@/utils/wrap'

export interface TabItem<K extends string> {
  key: K
  label: string
}

export function Tabs<K extends string>({
  items,
  value,
  onChange,
  idPrefix,
  label,
}: {
  items: readonly TabItem<K>[]
  value: K
  onChange: (key: K) => void
  idPrefix: string
  label: string
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  function onKeyDown(event: KeyboardEvent, index: number) {
    const step =
      event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    const next = wrapIndex(index, step, items.length)
    const item = items[next]
    if (!item) return
    onChange(item.key)
    refs.current[next]?.focus()
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      className="inline-flex shrink-0 gap-1 rounded-full bg-surface p-1"
    >
      {items.map((item, index) => {
        const selected = item.key === value
        return (
          <button
            key={item.key}
            ref={(element) => {
              refs.current[index] = element
            }}
            type="button"
            role="tab"
            id={tabId(idPrefix, item.key)}
            aria-selected={selected}
            aria-controls={panelId(idPrefix, item.key)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.key)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={`h-10 cursor-pointer rounded-full px-4 text-secondary transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              selected
                ? 'bg-bg font-semibold text-text shadow-popover'
                : 'text-text-muted hover:text-text'
            }`}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}

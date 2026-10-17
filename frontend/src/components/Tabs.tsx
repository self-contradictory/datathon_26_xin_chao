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
    <div role="tablist" aria-label={label} className="flex gap-2">
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
            className={`relative h-12 cursor-pointer px-4 text-body transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
              selected
                ? 'font-semibold text-text'
                : 'text-text-muted hover:text-text'
            }`}
          >
            {item.label}
            {selected && (
              <span
                aria-hidden="true"
                className="absolute inset-x-0 -bottom-px h-[3px] rounded-t-sm bg-brand"
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

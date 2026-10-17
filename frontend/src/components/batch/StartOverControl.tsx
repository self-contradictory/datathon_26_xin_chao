import { useEffect, useId, useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { PlusIcon } from '@/components/icons'
import { format, useStrings } from '@/i18n'

export function StartOverControl({
  unfinished,
  onConfirm,
}: {
  unfinished: number
  onConfirm: () => void
}) {
  const t = useStrings('batch')
  const questionId = useId()
  const [asking, setAsking] = useState(false)
  const startRef = useRef<HTMLButtonElement>(null)
  const continueRef = useRef<HTMLButtonElement>(null)
  const wasAsking = useRef(false)
  if (asking && unfinished === 0) setAsking(false)
  const open = asking && unfinished > 0

  useEffect(() => {
    if (open) continueRef.current?.focus()
    else if (wasAsking.current) startRef.current?.focus()
    wasAsking.current = open
  }, [open])

  function start() {
    if (unfinished > 0) setAsking(true)
    else onConfirm()
  }

  if (!open) {
    return (
      <Button
        ref={startRef}
        variant="secondary"
        icon={<PlusIcon size={20} />}
        onClick={start}
        className="self-start max-sm:w-full"
      >
        {t.startOver}
      </Button>
    )
  }

  return (
    <div
      role="group"
      aria-labelledby={questionId}
      className="flex flex-col gap-3 rounded-md border border-border p-4"
    >
      <p id={questionId} className="font-semibold">
        {format(t.confirmStop, { n: unfinished })}
      </p>
      <div className="flex flex-wrap gap-3">
        <Button
          ref={continueRef}
          onClick={() => setAsking(false)}
          className="max-sm:w-full"
        >
          {t.confirmNo}
        </Button>
        <Button
          variant="secondary"
          onClick={onConfirm}
          className="max-sm:w-full"
        >
          {t.confirmYes}
        </Button>
      </div>
    </div>
  )
}

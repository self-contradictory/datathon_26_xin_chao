import { useEffect, useId, useRef } from 'react'
import { Button } from './Button'

export function ConfirmBar({
  question,
  keepLabel,
  confirmLabel,
  onKeep,
  onConfirm,
}: {
  question: string
  keepLabel: string
  confirmLabel: string
  onKeep: () => void
  onConfirm: () => void
}) {
  const questionId = useId()
  const keepRef = useRef<HTMLButtonElement>(null)

  useEffect(() => keepRef.current?.focus(), [])

  return (
    <div
      role="group"
      aria-labelledby={questionId}
      className="flex flex-col gap-3 rounded-lg border border-border bg-bg p-4 shadow-card"
    >
      <p id={questionId} className="font-semibold">
        {question}
      </p>
      <div className="flex flex-wrap gap-3">
        <Button ref={keepRef} onClick={onKeep} className="max-sm:w-full">
          {keepLabel}
        </Button>
        <Button
          variant="secondary"
          onClick={onConfirm}
          className="max-sm:w-full"
        >
          {confirmLabel}
        </Button>
      </div>
    </div>
  )
}

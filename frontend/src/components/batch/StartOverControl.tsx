import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { ConfirmBar } from '@/components/ConfirmBar'
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
  const [asking, setAsking] = useState(false)
  const startRef = useRef<HTMLButtonElement>(null)
  const wasAsking = useRef(false)
  if (asking && unfinished === 0) setAsking(false)
  const open = asking && unfinished > 0

  useEffect(() => {
    if (!open && wasAsking.current) startRef.current?.focus()
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
    <ConfirmBar
      question={format(t.confirmStop, { n: unfinished })}
      keepLabel={t.confirmNo}
      confirmLabel={t.confirmYes}
      onKeep={() => setAsking(false)}
      onConfirm={onConfirm}
    />
  )
}

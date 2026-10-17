import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { ActModel } from './model'

const ROOT_ID = 'print-root'

function printRoot(): HTMLElement {
  const existing = document.getElementById(ROOT_ID)
  if (existing) return existing
  const root = document.createElement('div')
  root.id = ROOT_ID
  document.body.append(root)
  return root
}

async function whenReady(root: HTMLElement) {
  await document.fonts.ready
  const images = [...root.querySelectorAll('img')]
  await Promise.all(images.map((image) => image.decode().catch(() => {})))
}

export function usePrintAct() {
  const [job, setJob] = useState<{ model: ActModel; title: string } | null>(
    null,
  )
  const [root, setRoot] = useState<HTMLElement | null>(null)
  const cleanup = useRef<(() => void) | null>(null)

  const run = useEffectEvent(async (title: string, target: HTMLElement) => {
    await whenReady(target)
    cleanup.current?.()
    const previous = document.title
    const done = () => {
      window.removeEventListener('afterprint', done)
      document.title = previous
      document.body.classList.remove('printing-act')
      cleanup.current = null
      setJob(null)
    }
    cleanup.current = done
    document.title = title
    document.body.classList.add('printing-act')
    window.addEventListener('afterprint', done)
    window.print()
  })

  useEffect(() => {
    if (!job || !root) return
    void run(job.title, root)
  }, [job, root])

  function print(model: ActModel, title: string) {
    setRoot(printRoot())
    setJob({ model, title })
  }

  return { printing: job, root, print }
}

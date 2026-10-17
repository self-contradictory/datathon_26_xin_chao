import { useEffect, useEffectEvent, useState } from 'react'
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

  const run = useEffectEvent(async (title: string, target: HTMLElement) => {
    await whenReady(target)
    const previous = document.title
    document.title = title
    window.addEventListener(
      'afterprint',
      () => {
        document.title = previous
        setJob(null)
      },
      { once: true },
    )
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

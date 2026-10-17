import { useRef, useState, type DragEvent } from 'react'

export function carriesFiles(dataTransfer: DataTransfer | null): boolean {
  return dataTransfer?.types.includes('Files') ?? false
}

export function useFileDrop(onFile: (file: File) => void) {
  const [dragging, setDragging] = useState(false)
  const depth = useRef(0)

  const handlers = {
    onDragEnter(event: DragEvent<HTMLElement>) {
      if (!carriesFiles(event.dataTransfer)) return
      event.preventDefault()
      depth.current += 1
      setDragging(true)
    },
    onDragOver(event: DragEvent<HTMLElement>) {
      if (!carriesFiles(event.dataTransfer)) return
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
    },
    onDragLeave(event: DragEvent<HTMLElement>) {
      if (!carriesFiles(event.dataTransfer)) return
      const related = event.relatedTarget
      const leftZone =
        related instanceof Node && !event.currentTarget.contains(related)
      depth.current = leftZone ? 0 : Math.max(0, depth.current - 1)
      if (depth.current === 0) setDragging(false)
    },
    onDrop(event: DragEvent<HTMLElement>) {
      if (!carriesFiles(event.dataTransfer)) return
      event.preventDefault()
      depth.current = 0
      setDragging(false)
      const file = event.dataTransfer.files[0]
      if (file) onFile(file)
    },
  }

  return { dragging, handlers }
}

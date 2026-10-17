import { useEffect, useRef } from 'react'
import { Owl } from '@/components/Owl'
import { useStrings } from '@/i18n'
import { DropZone } from '@/components/upload/DropZone'
import type { UploadScreenProps } from './contracts'

export function UploadScreen({
  onSubmit,
  onSubmitMany,
  preview,
  focusTitle = false,
}: UploadScreenProps) {
  const t = useStrings('upload')
  const titleRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (focusTitle) titleRef.current?.focus()
  }, [focusTitle])
  return (
    <main className="flex min-h-[calc(100svh-65px)] flex-col items-center justify-center gap-8 px-4 pt-12 pb-16 sm:pt-16 sm:pb-24">
      <div className="flex flex-col items-center gap-4 text-center">
        <Owl mood="welcome" className="w-56 animate-float sm:w-72" />
        <h1
          ref={titleRef}
          tabIndex={-1}
          className="text-title font-bold focus:outline-none sm:text-[36px] sm:leading-11"
        >
          {t.title}
        </h1>
      </div>
      <DropZone
        onSubmit={onSubmit}
        onSubmitMany={onSubmitMany}
        preview={preview}
      />
    </main>
  )
}

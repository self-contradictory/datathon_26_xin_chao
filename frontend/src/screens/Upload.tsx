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
      <div className="flex w-full max-w-[760px] items-center justify-center gap-4 sm:gap-5">
        <Owl mood="hello" className="w-20 shrink-0 sm:w-28" />
        <h1
          ref={titleRef}
          tabIndex={-1}
          className="max-w-[16ch] text-title font-semibold focus:outline-none sm:max-w-none sm:whitespace-nowrap"
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

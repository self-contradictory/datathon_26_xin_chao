import { LockIcon } from '@/components/icons'
import { useStrings } from '@/i18n'
import { DropZone } from '@/components/upload/DropZone'
import type { UploadScreenProps } from './contracts'

export function UploadScreen({ onSubmit, preview }: UploadScreenProps) {
  const t = useStrings('upload')
  return (
    <main className="flex min-h-[calc(100svh-65px)] flex-col items-center justify-center gap-8 px-4 pt-12 pb-16 sm:pt-16 sm:pb-24">
      <div className="flex max-w-[640px] flex-col gap-2 text-center">
        <h1 className="text-title font-semibold">{t.title}</h1>
        <p className="text-text-muted">{t.subtitle}</p>
      </div>
      <DropZone onSubmit={onSubmit} preview={preview} />
      <p className="max-w-[640px] text-center text-secondary text-text-muted">
        <LockIcon size={20} className="mr-2 inline-block align-top" />
        {t.privacy}
      </p>
    </main>
  )
}

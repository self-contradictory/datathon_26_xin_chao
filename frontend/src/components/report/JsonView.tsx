import { useId } from 'react'
import type { DoneJob } from '@/api/types'
import { Button } from '@/components/Button'
import { CopyIcon } from '@/components/icons'
import { Toast } from '@/components/Toast'
import { useToast } from '@/components/useToast'
import { format, localeOf, useLang, useStrings } from '@/i18n'
import { copyText } from '@/utils/clipboard'
import { fullJson, screenJson } from './json'

export function JsonView({ job }: { job: DoneJob }) {
  const t = useStrings('jsonView')
  const locale = localeOf(useLang().lang)
  const toast = useToast()
  const titleId = useId()

  const plural = new Intl.PluralRules(locale)
  const lengthLabel = (n: number) => {
    const category = plural.select(n)
    const template =
      category === 'one'
        ? t.charsOne
        : category === 'few'
          ? t.charsFew
          : category === 'many'
            ? t.charsMany
            : t.charsOther
    return format(template, { n: n.toLocaleString(locale) })
  }

  async function copy() {
    const ok = await copyText(fullJson(job))
    toast.show(ok ? t.copied : t.copyFailed)
  }

  return (
    <section
      aria-labelledby={titleId}
      className="overflow-hidden rounded-md bg-surface"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border py-2 pr-2 pl-4">
        <div className="flex min-w-0 flex-col">
          <h2 id={titleId} className="text-secondary font-semibold">
            {t.title}
          </h2>
          <p className="text-caption text-text-muted">{t.note}</p>
        </div>
        <Button
          variant="secondary"
          icon={<CopyIcon size={20} />}
          onClick={() => void copy()}
        >
          {t.copy}
        </Button>
      </div>
      <div
        role="region"
        aria-label={t.code}
        tabIndex={0}
        className="overflow-x-auto focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand"
      >
        <pre className="w-fit p-4 font-mono text-secondary font-medium tabular-nums">
          {screenJson(job, lengthLabel)}
        </pre>
      </div>
      <Toast message={toast.message} />
    </section>
  )
}

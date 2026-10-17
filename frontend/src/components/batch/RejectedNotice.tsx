import { ErrorIcon } from '@/components/icons'
import { format, useStrings } from '@/i18n'
import type { RejectedFile } from '@/utils/file'

export function RejectedNotice({ rejected }: { rejected: RejectedFile[] }) {
  const t = useStrings('batch')

  return (
    <div className="flex gap-3 rounded-md bg-surface p-4">
      <ErrorIcon className="shrink-0 text-text" />
      <div className="flex min-w-0 flex-col gap-1">
        <p className="font-semibold">
          {format(t.rejectedTitle, { n: rejected.length })}
        </p>
        <ul>
          {rejected.map(({ fileName, problem }, index) => (
            <li key={index} className="wrap-anywhere">
              {format(problem.kind === 'empty' ? t.empty : t.notMov, {
                name: fileName,
              })}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

import type { RuleSource } from '@/api/types'
import { safeSourceUrl } from '@/ruleSource'
import { TextLink } from './TextLink'

export function SourceCitation({ source }: { source: RuleSource }) {
  const url = safeSourceUrl(source.url)
  return (
    <div className="flex flex-col items-start gap-2">
      <span>{source.document}</span>
      {source.clause && <span className="font-semibold">{source.clause}</span>}
      {url && (
        <TextLink href={url} label={source.document}>
          {url}
        </TextLink>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { InfoIcon } from '@/components/icons'
import { Owl } from '@/components/Owl'
import { RuleNorm } from '@/components/RuleNorm'
import { TextLink } from '@/components/TextLink'
import { format, useStrings } from '@/i18n'
import { RULES, type Rule } from '@/rules'

function RuleLink({ rule }: { rule: Rule }) {
  const t = useStrings('rules')
  const names = useStrings('violationTypes')
  if (!rule.url) {
    return (
      <>
        <span aria-hidden="true" className="text-text-muted">
          —
        </span>
        <span className="sr-only">{t.noLink}</span>
      </>
    )
  }
  return (
    <TextLink
      href={rule.url}
      external
      label={format(t.linkLabel, { type: names[rule.id] })}
    >
      adilet.zan.kz
    </TextLink>
  )
}

const TH =
  'border-b border-border px-4 py-3 text-left text-secondary font-semibold text-text-muted'
const TD = 'border-b border-border p-4 align-top'

const HAS_LINKS = RULES.some((rule) => rule.url)

const TABLE_SHOWN = HAS_LINKS ? 'md:block' : 'sm:block'
const CARDS_SHOWN = HAS_LINKS ? 'md:hidden' : 'sm:hidden'

function RulesTable({ highlight }: { highlight: string | null }) {
  const t = useStrings('rules')
  const looks = useStrings('ruleLooks')
  const names = useStrings('violationTypes')
  return (
    <div
      className={`hidden overflow-x-auto rounded-lg border border-border bg-bg shadow-card ${TABLE_SHOWN}`}
    >
      <table className="w-full border-collapse">
        <caption className="sr-only">{t.title}</caption>
        <thead>
          <tr className="bg-surface">
            <th scope="col" className={`${TH} w-[26%]`}>
              {t.colType}
            </th>
            <th scope="col" className={TH}>
              {t.colLooks}
            </th>
            <th
              scope="col"
              className={`${TH} ${HAS_LINKS ? 'w-[22%]' : 'w-[28%]'}`}
            >
              {t.colNorm}
            </th>
            {HAS_LINKS && (
              <th scope="col" className={`${TH} w-[14%]`}>
                {t.colLink}
              </th>
            )}
          </tr>
        </thead>
        <tbody className="[&>tr:last-child>*]:border-b-0">
          {RULES.map((rule) => (
            <tr
              key={rule.type}
              data-rule={rule.id}
              tabIndex={-1}
              className={`scroll-mt-24 transition-colors duration-200 focus:outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${highlight === rule.id ? 'bg-brand-tint' : ''}`}
            >
              <th scope="row" className={`${TD} text-left font-semibold`}>
                {names[rule.id]}
              </th>
              <td className={TD}>{looks[rule.id]}</td>
              <td className={TD}>
                <RuleNorm rule={rule} />
              </td>
              {HAS_LINKS && (
                <td className={`${TD} whitespace-nowrap`}>
                  <RuleLink rule={rule} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RulesCards({ highlight }: { highlight: string | null }) {
  const t = useStrings('rules')
  const looks = useStrings('ruleLooks')
  const names = useStrings('violationTypes')
  return (
    <ul className={`flex flex-col gap-3 ${CARDS_SHOWN}`}>
      {RULES.map((rule) => (
        <li
          key={rule.type}
          data-rule={rule.id}
          tabIndex={-1}
          className={`scroll-mt-24 rounded-lg border border-border p-4 shadow-card transition-colors duration-200 focus:outline-none focus-visible:outline-2 focus-visible:outline-brand ${highlight === rule.id ? 'bg-brand-tint' : 'bg-bg'}`}
        >
          <h2 className="text-body font-semibold">{names[rule.id]}</h2>
          <dl className="mt-3 flex flex-col gap-3">
            <div>
              <dt className="text-secondary text-text-muted">{t.colLooks}</dt>
              <dd>{looks[rule.id]}</dd>
            </div>
            <div>
              <dt className="text-secondary text-text-muted">{t.colNorm}</dt>
              <dd>
                <RuleNorm rule={rule} />
              </dd>
            </div>
            {rule.url && (
              <div>
                <dt className="text-secondary text-text-muted">{t.colLink}</dt>
                <dd className="mt-2.5">
                  <RuleLink rule={rule} />
                </dd>
              </div>
            )}
          </dl>
        </li>
      ))}
    </ul>
  )
}

const HIGHLIGHT_MS = 1500

function useRuleFocus(ruleId: string | undefined) {
  const [highlight, setHighlight] = useState<string | null>(null)

  useEffect(() => {
    if (!ruleId) return
    const target = [
      ...document.querySelectorAll<HTMLElement>(
        `[data-rule="${CSS.escape(ruleId)}"]`,
      ),
    ].find((element) => element.offsetParent !== null)
    if (!target) return
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    target.scrollIntoView({
      behavior: calm ? 'auto' : 'smooth',
      block: 'center',
    })
    target.focus({ preventScroll: true })
    const show = setTimeout(() => setHighlight(ruleId), 0)
    const hide = setTimeout(() => setHighlight(null), HIGHLIGHT_MS)
    return () => {
      clearTimeout(show)
      clearTimeout(hide)
    }
  }, [ruleId])

  return highlight
}

export function RulesPage({ focusRuleId }: { focusRuleId?: string }) {
  const t = useStrings('rules')
  const highlight = useRuleFocus(focusRuleId)
  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 pt-8 pb-12 sm:px-6 lg:pt-12 lg:pb-16">
      <div className="flex flex-col-reverse gap-6 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-title font-semibold">{t.title}</h1>
        <Owl mood="reading" className="w-48 shrink-0 rounded-lg sm:w-56" />
      </div>

      <RulesTable highlight={highlight} />
      <RulesCards highlight={highlight} />

      <div
        role="note"
        className="flex items-start gap-3 rounded-md bg-surface p-4"
      >
        <InfoIcon size={20} className="mt-0.5 shrink-0 text-text-muted" />
        <p className="max-w-[72ch]">{t.note}</p>
      </div>
    </main>
  )
}

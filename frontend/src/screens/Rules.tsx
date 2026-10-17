import { useEffect, useState } from 'react'
import { Owl } from '@/components/Owl'
import { RuleNorm } from '@/components/RuleNorm'
import { TextLink } from '@/components/TextLink'
import { format, useStrings } from '@/i18n'
import { ACT_URLS, RULES, ruleActs, type ActId, type Rule } from '@/rules'

function ActLink({ act }: { act: ActId }) {
  const t = useStrings('rules')
  const acts = useStrings('acts')
  return (
    <TextLink
      href={ACT_URLS[act]}
      label={format(t.linkLabel, { act: acts[act] })}
    >
      {acts[act]}
    </TextLink>
  )
}

function Requirement({ rule }: { rule: Rule }) {
  const t = useStrings('rules')
  const requires = useStrings('ruleRequires')
  const check = useStrings('ruleCheck')
  return (
    <div className="flex flex-col gap-2">
      <p>{requires[rule.id]}</p>
      <p>
        <span className="font-semibold">{t.check}: </span>
        {check[rule.id]}
      </p>
    </div>
  )
}

function Norm({ rule }: { rule: Rule }) {
  const applicability = useStrings('applicability')
  return (
    <div className="flex flex-col items-start gap-2">
      <p>
        <RuleNorm rule={rule} />
      </p>
      <span className="rounded-full bg-surface px-3 py-1 text-secondary font-semibold">
        {applicability[rule.applicability]}
      </span>
      <ul className="flex flex-col">
        {ruleActs(rule).map((act) => (
          <li key={act}>
            <ActLink act={act} />
          </li>
        ))}
      </ul>
    </div>
  )
}

const TH =
  'border-b border-border px-4 py-3 text-left text-secondary font-semibold text-text-muted'
const TD = 'border-b border-border p-4 align-top'

function RulesTable({ highlight }: { highlight: string | null }) {
  const t = useStrings('rules')
  const names = useStrings('violationTypes')
  return (
    <div className="hidden overflow-x-auto rounded-lg border border-border bg-bg shadow-card md:block">
      <table className="w-full border-collapse">
        <caption className="sr-only">{t.title}</caption>
        <thead>
          <tr className="bg-surface">
            <th scope="col" className={`${TH} w-[24%]`}>
              {t.colType}
            </th>
            <th scope="col" className={TH}>
              {t.colRequires}
            </th>
            <th scope="col" className={`${TH} w-[28%]`}>
              {t.colNorm}
            </th>
          </tr>
        </thead>
        <tbody className="[&>tr:last-child>*]:border-b-0">
          {RULES.map((rule) => (
            <tr
              key={rule.id}
              data-rule={rule.id}
              tabIndex={-1}
              className={`scroll-mt-24 transition-colors duration-200 focus:outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${highlight === rule.id ? 'bg-brand-tint' : ''}`}
            >
              <th scope="row" className={`${TD} text-left font-semibold`}>
                {names[rule.id]}
              </th>
              <td className={TD}>
                <Requirement rule={rule} />
              </td>
              <td className={TD}>
                <Norm rule={rule} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RulesCards({ highlight }: { highlight: string | null }) {
  const t = useStrings('rules')
  const names = useStrings('violationTypes')
  return (
    <ul className="flex flex-col gap-3 md:hidden">
      {RULES.map((rule) => (
        <li
          key={rule.id}
          data-rule={rule.id}
          tabIndex={-1}
          className={`scroll-mt-24 rounded-lg border border-border p-4 shadow-card transition-colors duration-200 focus:outline-none focus-visible:outline-2 focus-visible:outline-brand ${highlight === rule.id ? 'bg-brand-tint' : 'bg-bg'}`}
        >
          <h2 className="text-body font-semibold">{names[rule.id]}</h2>
          <dl className="mt-3 flex flex-col gap-3">
            <div>
              <dt className="text-secondary text-text-muted">
                {t.colRequires}
              </dt>
              <dd>
                <Requirement rule={rule} />
              </dd>
            </div>
            <div>
              <dt className="text-secondary text-text-muted">{t.colNorm}</dt>
              <dd>
                <Norm rule={rule} />
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  )
}

function Documents() {
  const t = useStrings('rules')
  const titles = useStrings('actTitles')
  const acts = Object.keys(ACT_URLS) as ActId[]
  return (
    <section aria-labelledby="rules-documents" className="flex flex-col gap-3">
      <h2 id="rules-documents" className="text-section font-semibold">
        {t.documents}
      </h2>
      <ul className="flex flex-col gap-3 rounded-lg border border-border bg-bg p-4 shadow-card sm:p-6">
        {acts.map((act) => (
          <li key={act} className="flex flex-col gap-1">
            <p>{titles[act]}</p>
            <ActLink act={act} />
          </li>
        ))}
      </ul>
    </section>
  )
}

const HIGHLIGHT_MS = 2500

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
      <Documents />
    </main>
  )
}

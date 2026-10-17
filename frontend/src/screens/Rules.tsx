import { InfoIcon } from '@/components/icons'
import { Owl } from '@/components/Owl'
import { RuleNorm } from '@/components/RuleNorm'
import { TextLink } from '@/components/TextLink'
import { format, useStrings } from '@/i18n'
import { RULES, type Rule } from '@/rules'

function RuleLink({ rule }: { rule: Rule }) {
  const t = useStrings('rules')
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
      label={format(t.linkLabel, { type: rule.type })}
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

function RulesTable() {
  const t = useStrings('rules')
  const looks = useStrings('ruleLooks')
  return (
    <div
      className={`hidden overflow-x-auto rounded-md border border-border bg-bg shadow-card ${TABLE_SHOWN}`}
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
            <tr key={rule.type}>
              <th
                scope="row"
                lang="ru"
                className={`${TD} text-left font-semibold`}
              >
                {rule.type}
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

function RulesCards() {
  const t = useStrings('rules')
  const looks = useStrings('ruleLooks')
  return (
    <ul className={`flex flex-col gap-3 ${CARDS_SHOWN}`}>
      {RULES.map((rule) => (
        <li
          key={rule.type}
          className="rounded-md border border-border bg-bg p-4 shadow-card"
        >
          <h2 lang="ru" className="text-body font-semibold">
            {rule.type}
          </h2>
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

export function RulesPage() {
  const t = useStrings('rules')
  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 pt-8 pb-16 sm:px-6 sm:pt-12">
      <div className="flex flex-col-reverse gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex max-w-[72ch] flex-col gap-2">
          <h1 className="text-title font-semibold">{t.title}</h1>
          <p className="text-text-muted">{t.subtitle}</p>
        </div>
        <Owl mood="reading" className="w-48 shrink-0 rounded-lg sm:w-56" />
      </div>

      <RulesTable />
      <RulesCards />

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

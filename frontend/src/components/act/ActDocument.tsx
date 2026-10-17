import type { ReactNode } from 'react'
import { Owl } from '@/components/Owl'
import { RuleNorm } from '@/components/RuleNorm'
import { useViolationText } from '@/components/report/violationText'
import { format, localeOf, useLang, useStrings } from '@/i18n'
import { jpegDataUrl } from '@/utils/frames'
import {
  formatFileSize,
  formatFrameTime,
  formatFullDate,
  formatTime,
} from '@/utils/time'
import { ACT_URLS, ruleActs } from '@/rules'
import type { ActModel, ActViolation } from './model'

const CELL = 'border border-border px-2 py-1.5 text-left align-top'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <tr>
      <th scope="row" className={`${CELL} w-[32%] font-semibold`}>
        {label}
      </th>
      <td className={`${CELL} break-all`}>{children}</td>
    </tr>
  )
}

function Decision({ violation }: { violation: ActViolation }) {
  const t = useStrings('act')
  const review = useStrings('review')
  if (violation.decision === 'confirmed') return <>{review.confirmed}</>
  if (violation.decision === 'rejected') return <>{review.rejected}</>
  return <>{t.noDecision}</>
}

function Rule({ violation }: { violation: ActViolation }) {
  return violation.rule ? <RuleNorm rule={violation.rule} /> : <>—</>
}

function ViolationBlock({ violation }: { violation: ActViolation }) {
  const t = useStrings('act')
  const card = useStrings('violationCard')
  const requires = useStrings('ruleRequires')
  const check = useStrings('ruleCheck')
  const { typeName, typeLang } = useViolationText()

  return (
    <section className="act-block mt-5 flex flex-col gap-2">
      <h3 className="text-[13px] font-semibold">
        {violation.position}. {formatTime(violation.timecode)} ·{' '}
        <span lang={typeLang(violation.type)}>{typeName(violation.type)}</span>
      </h3>
      <div className="grid max-w-[420px] grid-cols-3 gap-2">
        {violation.frames.map((frame, k) => (
          <figure key={k} className="flex flex-col gap-1">
            <img
              src={jpegDataUrl(frame.image_base64)}
              alt=""
              className="aspect-[9/16] w-full rounded-sm object-cover"
            />
            <figcaption className="text-[10px]">
              {format(t.frame, {
                k: k + 1,
                time: formatFrameTime(frame.timestamp_sec),
              })}
            </figcaption>
          </figure>
        ))}
      </div>
      <p className="text-[12px]">
        <span className="font-semibold">{card.description}: </span>
        <span lang="ru">{violation.source.description}</span>
      </p>
      {violation.rule && (
        <>
          <p className="text-[12px]">
            <span className="font-semibold">{card.requires}: </span>
            {requires[violation.rule.id]}
          </p>
          <p className="text-[12px]">
            <span className="font-semibold">{card.check}: </span>
            {check[violation.rule.id]}
          </p>
        </>
      )}
      <p className="text-[12px]">
        <span className="font-semibold">{card.rule}: </span>
        <Rule violation={violation} />
      </p>
      <p className="text-[12px]">
        <span className="font-semibold">{t.colDecision}: </span>
        <Decision violation={violation} />
      </p>
    </section>
  )
}

export function ActDocument({ model }: { model: ActModel }) {
  const t = useStrings('act')
  const rulesText = useStrings('rules')
  const titles = useStrings('actTitles')
  const acts = [
    ...new Set(
      model.violations.flatMap((violation) =>
        violation.rule ? ruleActs(violation.rule) : [],
      ),
    ),
  ]
  const verdict = useStrings('verdictSummary')
  const units = useStrings('units')
  const locale = localeOf(useLang().lang)
  const { typeName, typeLang } = useViolationText()
  const { review } = model

  return (
    <article className="flex flex-col gap-4 bg-bg text-[12px] leading-5 text-text">
      <header className="flex items-center justify-between gap-4 border-b-2 border-brand pb-3">
        <div className="flex items-center gap-3">
          <Owl mood="idle" className="w-10" />
          <h1 className="text-[18px] font-bold">{t.title}</h1>
        </div>
        <div className="text-right">
          <p className="font-semibold">
            {format(t.number, { n: model.number })}
          </p>
          <p>{formatFullDate(model.checkedAt)}</p>
        </div>
      </header>

      <section className="act-block flex flex-col gap-2">
        <h2 className="text-[14px] font-semibold">{t.object}</h2>
        <table className="w-full border-collapse">
          <tbody>
            <Field label={t.file}>{model.fileName}</Field>
            <Field label={t.size}>
              {formatFileSize(model.fileSize, locale, units)}
            </Field>
            {model.duration !== null && (
              <Field label={t.duration}>{formatTime(model.duration)}</Field>
            )}
            <Field label={t.hash}>{model.fileHash ?? t.noHash}</Field>
            <Field label={t.job}>{model.jobId}</Field>
          </tbody>
        </table>
      </section>

      <section className="act-block flex flex-col gap-1">
        <h2 className="text-[14px] font-semibold">{t.result}</h2>
        <p
          className={`text-[20px] leading-7 font-bold ${
            model.violation ? 'text-danger-text' : 'text-success-text'
          }`}
        >
          {model.violation
            ? format(verdict.violation, { n: model.violations.length })
            : verdict.clean}
        </p>
        {review.total > 0 && (
          <p>
            {format(t.reviewed, {
              confirmed: review.confirmed,
              rejected: review.rejected,
            })}
            {!review.complete &&
              ` · ${format(t.pending, { n: review.total - review.reviewed })}`}
          </p>
        )}
      </section>

      {model.violations.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-[14px] font-semibold">{t.violations}</h2>
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th scope="col" className={`${CELL} w-[6%]`}>
                  {t.colNumber}
                </th>
                <th scope="col" className={`${CELL} w-[10%]`}>
                  {t.colTime}
                </th>
                <th scope="col" className={CELL}>
                  {t.colType}
                </th>
                <th scope="col" className={`${CELL} w-[30%]`}>
                  {t.colRule}
                </th>
                <th scope="col" className={`${CELL} w-[16%]`}>
                  {t.colDecision}
                </th>
              </tr>
            </thead>
            <tbody>
              {model.violations.map((violation) => (
                <tr key={violation.index} className="act-block">
                  <td className={CELL}>{violation.position}</td>
                  <td className={`${CELL} tabular-nums`}>
                    {formatTime(violation.timecode)}
                  </td>
                  <td className={CELL} lang={typeLang(violation.type)}>
                    {typeName(violation.type)}
                  </td>
                  <td className={CELL}>
                    <Rule violation={violation} />
                  </td>
                  <td className={CELL}>
                    <Decision violation={violation} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {model.violations.map((violation) => (
            <ViolationBlock key={violation.index} violation={violation} />
          ))}
        </section>
      )}

      {acts.length > 0 && (
        <section className="act-block flex flex-col gap-1">
          <h2 className="text-[14px] font-semibold">{rulesText.documents}</h2>
          <ul className="flex flex-col gap-1">
            {acts.map((act) => (
              <li key={act}>
                <p>{titles[act]}</p>
                <p>{ACT_URLS[act]}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="act-block mt-6 pt-2">{t.signature}</footer>
    </article>
  )
}

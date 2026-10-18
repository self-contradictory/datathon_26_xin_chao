import { describe, expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { parseJobResponse } from '@/api/parse'
import type { RuleSource, Violation } from '@/api/types'
import { ActDocument } from '@/components/act/ActDocument'
import { buildReportModel } from '@/components/act/model'
import { findRule } from '@/rules'
import { violationDetails } from '@/ruleSource'
import { ViolationDetails } from './ViolationDetails'

const document =
  'Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей (постановление Правления НБРК от 29.11.2019 № 231)'
const url = 'https://adilet.zan.kz/rus/docs/V1900019680'
const approval = ' The rule is still a candidate awaiting legal review.'
const phone: Violation = {
  type: 'Cashier uses a mobile phone in the cash room',
  timecode_sec: 6,
  description: `Violation: Cashier uses a mobile phone in the cash room. Seen on video: the trigger itself is prohibited. Rule: ${document}, п. 12.${approval}`,
  evidence_frames: [{ timestamp_sec: 6, image_base64: 'AAAA' }],
}

function render(violation: Violation): string {
  return renderToStaticMarkup(
    <ViolationDetails
      violation={violation}
      decision={null}
      onDecide={() => {}}
      clip={null}
    />,
  )
}

function norm(html: string): string {
  return html.slice(html.indexOf('>Норма</dt>'))
}

describe('finding source in the report', () => {
  test('the screenshot response shows its source under Норма', () => {
    const html = render(phone)
    expect(norm(html)).toContain(document)
    expect(norm(html)).toContain('п. 12')
    expect(norm(html)).toContain(`href="${url}"`)
    expect(html).not.toContain('Тип не из списка правил')
    expect(html.slice(0, html.indexOf('>Норма</dt>'))).not.toContain(document)
    expect(html).toContain(approval.trim())
    expect(findRule(phone.type)?.id).toBe('mobilePhone')
    expect(findRule('CD25-MOBILE-PHONE-IN-CASH-ROOM')?.id).toBe('mobilePhone')
  })

  test('structured metadata takes precedence over description and local rules', () => {
    const source: RuleSource = {
      document: 'Внутренний регламент банка',
      clause: 'Раздел 3.2',
      url: 'https://example.com/policy#section-3',
      verified: false,
    }
    const job = parseJobResponse({
      job_id: 'structured',
      status: 'done',
      verdict: 'violation',
      violations: [
        {
          ...phone,
          type: 'New finding',
          rule_id: 'CD25-MOBILE-PHONE-IN-CASH-ROOM',
          source,
        },
      ],
    })
    const violation = job.violations![0]!
    const html = render(violation)
    expect(norm(html)).toContain(source.document)
    expect(norm(html)).toContain(source.clause!)
    expect(norm(html)).toContain(`href="${source.url}"`)
    expect(norm(html)).not.toContain(document)
    expect(html).not.toContain('Тип не из списка правил')

    const model = buildReportModel(
      {
        jobId: job.job_id,
        result: job,
        createdAt: 1000,
        fileName: 'phone.mov',
        fileSize: 1,
        fileHash: null,
        review: {},
      },
      null,
    )
    const act = renderToStaticMarkup(<ActDocument model={model} />)
    expect(act).toContain(source.document)
    expect(act).toContain(source.clause!)
    expect(act).toContain(`href="${source.url}"`)
  })

  test('legacy citations also work for types outside the local rule list', () => {
    const html = render({ ...phone, type: 'Unknown finding' })
    expect(norm(html)).toContain(document)
    expect(norm(html)).toContain(`href="${url}"`)
    expect(html).not.toContain('Тип не из списка правил')
  })

  test('unknown documents stay readable without inventing a source URL', () => {
    const details = violationDetails({
      ...phone,
      description: 'Observed something. Rule: Internal policy, section 3.',
    })
    expect(details.description).toBe('Observed something.')
    expect(details.source?.document).toBe('Internal policy, section 3')
    expect(details.source?.url).toBeNull()
  })

  test('a source without a clause or URL still displays its document', () => {
    const html = render({
      ...phone,
      type: 'Unknown finding',
      description: 'Observed something.',
      source: { document: 'Внутренний регламент', clause: null, url: null },
    })
    expect(norm(html)).toContain('Внутренний регламент')
    expect(norm(html)).not.toContain('href=')
  })

  test('unsafe source URLs are never rendered as links', () => {
    const html = render({
      ...phone,
      source: { document, clause: 'п. 12', url: 'javascript:alert(1)' },
    })
    expect(norm(html)).toContain(document)
    expect(norm(html)).not.toContain('href=')
  })

  test('known fixture types keep their norm and unknown types keep the fallback', () => {
    const fixture = { ...phone, description: 'Телефон виден на видео.' }
    expect(
      norm(render({ ...fixture, type: 'Мобильный телефон в кассовом узле' })),
    ).toContain('п. 12')
    expect(render({ ...fixture, type: 'Unknown finding' })).toContain(
      'Тип не из списка правил',
    )
  })
})

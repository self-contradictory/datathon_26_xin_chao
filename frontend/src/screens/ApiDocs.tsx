import { Toast } from '@/components/Toast'
import { useToast } from '@/components/useToast'
import { useStrings } from '@/i18n'
import { CodeBlock } from '@/components/docs/CodeBlock'
import { DocSection, DocSubheading } from '@/components/docs/DocSection'
import { Code } from '@/components/docs/Inline'
import { Template } from '@/components/Template'
import { MethodBadge } from '@/components/docs/MethodBadge'
import {
  ANALYZE_RESPONSE,
  analyzeCurl,
  apiBase,
  authHeader,
  JOB_RESPONSE,
  jobCurl,
  toJson,
} from './apiExamples'

export function ApiDocsPage() {
  const t = useStrings('apiDocs')
  const toast = useToast()

  const errors: [code: number, text: string][] = [
    [401, t.e401],
    [404, t.e404],
    [415, t.e415],
  ]

  return (
    <main className="mx-auto flex w-full max-w-[960px] flex-col gap-12 px-4 pt-8 pb-16 sm:px-6 sm:pt-12">
      <div className="flex max-w-[72ch] flex-col gap-2">
        <h1 className="text-title font-semibold">{t.title}</h1>
        <p className="text-text-muted">{t.subtitle}</p>
      </div>

      <DocSection id="api-auth" heading={t.authTitle}>
        <p className="max-w-[72ch]">
          <Template
            text={t.authText}
            values={{
              header: <Code pill>X-API-Key</Code>,
              base: (
                <span className="whitespace-nowrap">
                  <Code>{apiBase(t.host)}</Code>
                </span>
              ),
            }}
          />
        </p>
        <CodeBlock
          label={t.headerLabel}
          code={authHeader(t.key)}
          notify={toast.show}
        />
      </DocSection>

      <DocSection
        id="api-analyze"
        divided
        heading={
          <>
            <MethodBadge method="POST" />
            <span className="min-w-0 font-mono font-medium break-all">
              /api/v1/analyze
            </span>
          </>
        }
      >
        <p className="max-w-[72ch]">
          <Template
            text={t.analyzeText}
            values={{ jobId: <Code>job_id</Code>, file: <Code>file</Code> }}
          />
        </p>
        <DocSubheading>{t.requestExample}</DocSubheading>
        <CodeBlock
          label="cURL"
          context="POST /api/v1/analyze"
          code={analyzeCurl(t.host)}
          notify={toast.show}
        />
        <DocSubheading>{t.response}</DocSubheading>
        <CodeBlock
          label="JSON"
          context="POST /api/v1/analyze"
          code={toJson(ANALYZE_RESPONSE)}
          notify={toast.show}
        />
      </DocSection>

      <DocSection
        id="api-job"
        divided
        heading={
          <>
            <MethodBadge method="GET" />
            <span className="min-w-0 font-mono font-medium break-all">
              /api/v1/jobs/{'{job_id}'}
            </span>
          </>
        }
      >
        <p className="max-w-[72ch]">
          <Template
            text={t.jobText}
            values={{
              status: <Code>status</Code>,
              processing: <Code>processing</Code>,
              done: <Code>done</Code>,
              failed: <Code>failed</Code>,
              verdict: <Code>verdict</Code>,
              violation: <Code>violation</Code>,
              noViolation: <Code>no_violation</Code>,
              type: <Code>type</Code>,
              rules: (
                <a
                  href="#/rules"
                  className="rounded-sm text-brand underline underline-offset-2 hover:text-brand-hover focus-visible:outline-2 focus-visible:outline-brand"
                >
                  {t.rulesLink}
                </a>
              ),
            }}
          />
        </p>
        <p className="max-w-[72ch]">
          <Template
            text={t.jobPolling}
            values={{
              processing: <Code>processing</Code>,
              verdict: <Code>verdict</Code>,
              violations: <Code>violations</Code>,
              null: <Code>null</Code>,
              noViolation: <Code>no_violation</Code>,
            }}
          />
        </p>
        <DocSubheading>{t.requestExample}</DocSubheading>
        <CodeBlock
          label="cURL"
          context="GET /api/v1/jobs/{job_id}"
          code={jobCurl(t.host)}
          notify={toast.show}
        />
        <DocSubheading>{t.jobResponse}</DocSubheading>
        <CodeBlock
          label="JSON"
          context="GET /api/v1/jobs/{job_id}"
          code={toJson(JOB_RESPONSE)}
          notify={toast.show}
        />
      </DocSection>

      <DocSection id="api-errors" divided heading={t.errorsTitle}>
        <div className="overflow-hidden rounded-md border border-border">
          <table
            aria-labelledby="api-errors"
            className="w-full border-collapse"
          >
            <tbody className="[&>tr:last-child>*]:border-b-0">
              {errors.map(([code, text]) => (
                <tr key={code}>
                  <th
                    scope="row"
                    className="w-16 border-b border-border px-4 py-3 text-left align-top font-mono text-secondary leading-6 font-medium tabular-nums sm:w-[120px]"
                  >
                    {code}
                  </th>
                  <td className="border-b border-border px-4 py-3 align-top">
                    {text}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DocSection>

      <Toast message={toast.message} />
    </main>
  )
}

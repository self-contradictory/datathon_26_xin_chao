import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { parseAnalyzeResponse, parseJobResponse } from '../src/api/parse'
import type { JobResponse } from '../src/api/types'

export const FRONTEND_DIR = join(import.meta.dir, '..')
export const BACKEND_DIR = join(FRONTEND_DIR, '..', 'backend')
export const DATASET_DIR = join(FRONTEND_DIR, '..', 'data', 'open', 'videos')
export const FRONTEND_URL = 'http://127.0.0.1:3000'
export const BACKEND_URL = 'http://127.0.0.1:8000'

const ENV_FILE = join(FRONTEND_DIR, '.env.local')
const KEY_ALPHABET =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'

function newApiKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(43))
  const secret = [...bytes]
    .map((byte) => KEY_ALPHABET[byte % KEY_ALPHABET.length])
    .join('')
  return `xc_${secret}`
}

export function ensureDevKey(): string {
  const text = existsSync(ENV_FILE) ? readFileSync(ENV_FILE, 'utf8') : ''
  const found = /^API_KEY=(xc_\w+)\s*$/m.exec(text)
  if (found?.[1]) return found[1]
  const key = newApiKey()
  const lines = text
    .split('\n')
    .filter((line) => line && !line.startsWith('API_KEY='))
  writeFileSync(ENV_FILE, [...lines, `API_KEY=${key}`, ''].join('\n'), {
    mode: 0o600,
  })
  return key
}

export async function reachable(url: string, init?: RequestInit) {
  try {
    return await fetch(url, { ...init, signal: AbortSignal.timeout(2000) })
  } catch {
    return null
  }
}

export async function waitFor(
  what: string,
  check: () => Promise<boolean>,
  timeoutMs: number,
) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await check()) return
    await Bun.sleep(500)
  }
  throw new Error(`${what} did not start within ${timeoutMs / 1000} s`)
}

export interface SmokeResult {
  file: string
  job: JobResponse
  seconds: number
}

export async function smokeTest(
  baseUrl: string,
  fileName = 'Х-17.mov',
): Promise<SmokeResult> {
  const page = await reachable(baseUrl)
  if (!page?.ok) throw new Error(`the site at ${baseUrl} does not answer`)

  const path = join(DATASET_DIR, fileName)
  const form = new FormData()
  form.append('file', Bun.file(path), fileName)
  const started = Date.now()
  const upload = await fetch(`${baseUrl}/api/v1/analyze`, {
    method: 'POST',
    body: form,
  })
  if (!upload.ok) {
    throw new Error(
      `upload failed: HTTP ${upload.status} ${await upload.text()}`,
    )
  }
  const { job_id } = parseAnalyzeResponse(await upload.json())

  const deadline = started + 5 * 60 * 1000
  while (Date.now() < deadline) {
    const reply = await fetch(`${baseUrl}/api/v1/jobs/${job_id}`)
    if (!reply.ok) throw new Error(`polling failed: HTTP ${reply.status}`)
    const job = parseJobResponse(await reply.json())
    if (job.status !== 'processing') {
      return { file: fileName, job, seconds: (Date.now() - started) / 1000 }
    }
    await Bun.sleep(1000)
  }
  throw new Error('the job did not finish within 5 minutes')
}

export function describeResult({ file, job, seconds }: SmokeResult): string {
  const found =
    job.status === 'done'
      ? `${job.verdict}, violations: ${job.violations?.length ?? 0}`
      : 'failed'
  return `${file} -> ${job.status} (${found}) in ${seconds.toFixed(1)} s`
}

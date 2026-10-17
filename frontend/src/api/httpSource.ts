import { parseAnalyzeResponse, parseJobResponse } from './parse'
import { ANALYZE_PATH, apiUrl, jobPath } from './paths'
import { JobError, type JobSource } from './source'

export type Fetch = (url: string, init: RequestInit) => Promise<Response>

export interface HttpSourceOptions {
  baseUrl: string
  apiKey: string
  responseTimeoutMs?: number
  createRequest?: () => XMLHttpRequest
  fetch?: Fetch
}

export function errorForStatus(status: number): JobError {
  if (status === 401 || status === 403) return new JobError('unauthorized')
  if (status === 404) return new JobError('not_found')
  if (status === 413 || status === 415 || status === 422) {
    return new JobError('bad_file')
  }
  if (status === 502 || status === 503 || status === 504) {
    return new JobError('network', `HTTP ${status}`)
  }
  return new JobError('server', `HTTP ${status}`)
}

function parseJsonBody<T>(text: string, parse: (value: unknown) => T): T {
  let body: unknown
  try {
    body = JSON.parse(text)
  } catch {
    throw new JobError('bad_response', 'response is not JSON')
  }
  return parse(body)
}

function linkedController(signal: AbortSignal | undefined) {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  return {
    signal: controller.signal,
    abort,
    unlink: () => signal?.removeEventListener('abort', abort),
  }
}

export function createHttpSource({
  baseUrl,
  apiKey,
  responseTimeoutMs = 15_000,
  createRequest = () => new XMLHttpRequest(),
  fetch = (url, init) => globalThis.fetch(url, init),
}: HttpSourceOptions): JobSource {
  const headers: Record<string, string> = apiKey ? { 'X-API-Key': apiKey } : {}

  return {
    upload(file, onProgress, signal) {
      return new Promise((resolve, reject) => {
        if (signal?.aborted) return reject(new JobError('aborted'))
        const request = createRequest()
        const cancel = () => request.abort()
        const settle = () => signal?.removeEventListener('abort', cancel)

        request.open('POST', apiUrl(baseUrl, ANALYZE_PATH))
        for (const [name, value] of Object.entries(headers)) {
          request.setRequestHeader(name, value)
        }
        request.upload.onprogress = (event) => {
          if (event.lengthComputable && event.total > 0) {
            onProgress(Math.min(0.99, event.loaded / event.total))
          }
        }
        request.onload = () => {
          settle()
          if (request.status < 200 || request.status >= 300) {
            return reject(errorForStatus(request.status))
          }
          try {
            const response = parseJsonBody(
              request.responseText,
              parseAnalyzeResponse,
            )
            onProgress(1)
            resolve(response)
          } catch (error) {
            reject(error)
          }
        }
        request.onerror = () => {
          settle()
          reject(new JobError('network'))
        }
        request.onabort = () => {
          settle()
          reject(new JobError('aborted'))
        }
        signal?.addEventListener('abort', cancel, { once: true })

        const body = new FormData()
        body.append('file', file, file.name)
        onProgress(0)
        request.send(body)
      })
    },

    async getJob(jobId, signal) {
      const request = linkedController(signal)
      let timedOut = false
      const timer = setTimeout(() => {
        timedOut = true
        request.abort()
      }, responseTimeoutMs)
      const failure = () => {
        if (signal?.aborted) return new JobError('aborted')
        return new JobError(
          'network',
          timedOut ? 'no response in time' : undefined,
        )
      }

      try {
        let response: Response
        try {
          response = await fetch(apiUrl(baseUrl, jobPath(jobId)), {
            headers,
            signal: request.signal,
            cache: 'no-store',
          })
        } catch {
          throw failure()
        } finally {
          clearTimeout(timer)
        }
        if (!response.ok) throw errorForStatus(response.status)
        let text: string
        try {
          text = await response.text()
        } catch {
          throw failure()
        }
        return parseJsonBody(text, parseJobResponse)
      } finally {
        request.unlink()
      }
    },
  }
}

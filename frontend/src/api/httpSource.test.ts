import { describe, expect, test } from 'bun:test'
import { createHttpSource, type Fetch } from './httpSource'
import { JobError } from './source'
import type { JobResponse } from './types'

type Listener = ((event: ProgressEvent) => void) | null

class FakeRequest {
  static last: FakeRequest
  method = ''
  url = ''
  headers: Record<string, string> = {}
  body: FormData | null = null
  status = 0
  responseText = ''
  aborted = false
  upload: { onprogress: Listener } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null

  constructor() {
    FakeRequest.last = this
  }
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }
  send(body: FormData) {
    this.body = body
  }
  abort() {
    this.aborted = true
    this.onabort?.()
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded,
      total,
    } as ProgressEvent)
  }
  respond(status: number, body: string) {
    this.status = status
    this.responseText = body
    this.onload?.()
  }
}

const file = new File([new Uint8Array([1, 2, 3])], 'Х-17.mov')

const done: JobResponse = {
  job_id: 'abc',
  status: 'done',
  verdict: 'no_violation',
  violations: [],
}

const hang: Fetch = (_, init) =>
  new Promise<Response>((_, reject) => {
    init.signal?.addEventListener('abort', () =>
      reject(new DOMException('aborted', 'AbortError')),
    )
  })

const reply =
  (status: number, body: string): Fetch =>
  async () =>
    new Response(body, { status })

function source(fetch?: Fetch, apiKey = 'xc_key') {
  return createHttpSource({
    baseUrl: 'https://api.example.kz/',
    apiKey,
    createRequest: () => new FakeRequest() as unknown as XMLHttpRequest,
    fetch: fetch ?? reply(200, '{}'),
    responseTimeoutMs: 50,
  })
}

async function kindOf(promise: Promise<unknown>): Promise<string> {
  try {
    await promise
  } catch (error) {
    if (error instanceof JobError) return error.kind
    throw error
  }
  throw new Error('expected a JobError')
}

describe('upload', () => {
  test('posts the file with the key and reports progress up to 1', async () => {
    const progress: number[] = []
    const pending = source().upload(file, (f) => progress.push(f))
    const request = FakeRequest.last
    request.progress(50, 100)
    request.progress(100, 100)
    request.respond(200, '{"job_id":"abc"}')
    expect(await pending).toEqual({ job_id: 'abc' })
    expect(request.method).toBe('POST')
    expect(request.url).toBe('https://api.example.kz/api/v1/analyze')
    expect(request.headers['X-API-Key']).toBe('xc_key')
    expect((request.body!.get('file') as File).name).toBe('Х-17.mov')
    expect(progress).toEqual([0, 0.5, 0.99, 1])
  })

  test('sends no key header when no key is configured', async () => {
    const pending = source(undefined, '').upload(file, () => {})
    FakeRequest.last.respond(200, '{"job_id":"abc"}')
    await pending
    expect(FakeRequest.last.headers).toEqual({})
  })

  test('maps HTTP errors to error kinds', async () => {
    const cases: [number, string][] = [
      [401, 'unauthorized'],
      [403, 'unauthorized'],
      [404, 'not_found'],
      [413, 'bad_file'],
      [415, 'bad_file'],
      [422, 'bad_file'],
      [500, 'server'],
      [502, 'network'],
      [503, 'network'],
      [504, 'network'],
    ]
    for (const [status, kind] of cases) {
      const pending = source().upload(file, () => {})
      FakeRequest.last.respond(status, '{"detail":"x"}')
      expect(await kindOf(pending)).toBe(kind)
    }
  })

  test('a body that is not the schema is a bad_response', async () => {
    const notJson = source().upload(file, () => {})
    FakeRequest.last.respond(200, '<html>')
    expect(await kindOf(notJson)).toBe('bad_response')
    const noId = source().upload(file, () => {})
    FakeRequest.last.respond(200, '{}')
    expect(await kindOf(noId)).toBe('bad_response')
  })

  test('a network failure is a network error', async () => {
    const pending = source().upload(file, () => {})
    FakeRequest.last.onerror?.()
    expect(await kindOf(pending)).toBe('network')
  })

  test('aborting cancels the request', async () => {
    const controller = new AbortController()
    const pending = source().upload(file, () => {}, controller.signal)
    controller.abort()
    expect(await kindOf(pending)).toBe('aborted')
    expect(FakeRequest.last.aborted).toBe(true)
  })
})

describe('getJob', () => {
  test('gets the job with the key and parses it', async () => {
    let seen: { url: string; key: string | null } | null = null
    const fetch: Fetch = async (url, init) => {
      seen = { url, key: new Headers(init.headers).get('X-API-Key') }
      return Response.json(done)
    }
    expect(await source(fetch).getJob('a b')).toEqual(done)
    expect(seen!).toEqual({
      url: 'https://api.example.kz/api/v1/jobs/a%20b',
      key: 'xc_key',
    })
  })

  test('maps statuses and broken bodies', async () => {
    const kind = (fetch: Fetch) => kindOf(source(fetch).getJob('x'))
    expect(await kind(reply(404, '{}'))).toBe('not_found')
    expect(await kind(reply(401, '{}'))).toBe('unauthorized')
    expect(await kind(reply(500, ''))).toBe('server')
    expect(await kind(reply(200, 'oops'))).toBe('bad_response')
    expect(await kind(reply(200, '{"job_id":"x","status":"queued"}'))).toBe(
      'bad_response',
    )
  })

  test('no response in time is a network error, so polling retries', async () => {
    expect(await kindOf(source(hang).getJob('x'))).toBe('network')
  })

  test('a body that breaks off is a network error too', async () => {
    const brokenBody: Fetch = async () =>
      new Response(
        new ReadableStream({
          start(controller) {
            controller.error(new TypeError('connection reset'))
          },
        }),
      )
    expect(await kindOf(source(brokenBody).getJob('x'))).toBe('network')
  })

  test('the caller can abort polling', async () => {
    const controller = new AbortController()
    const pending = source(hang).getJob('x', controller.signal)
    controller.abort()
    expect(await kindOf(pending)).toBe('aborted')
  })
})

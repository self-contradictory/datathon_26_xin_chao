import { describe, expect, test } from 'bun:test'
import { CheckFailure, runCheck } from './check'
import { JobError, type JobSource } from './source'
import type { JobResponse } from './types'

const file = new File([new Uint8Array([1])], 'Х-17.mov')
const done: JobResponse = {
  job_id: 'j',
  status: 'done',
  verdict: 'no_violation',
  violations: [],
}

function source(
  upload: JobSource['upload'],
  replies: (JobResponse | JobError)[],
): JobSource {
  let call = 0
  return {
    upload,
    getJob: async () => {
      const reply = replies[Math.min(call++, replies.length - 1)]!
      if (reply instanceof JobError) throw reply
      return reply
    },
  }
}

const accept: JobSource['upload'] = async (_file, onProgress) => {
  onProgress(0.5)
  onProgress(1)
  return { job_id: 'j' }
}

async function failureOf(promise: Promise<unknown>): Promise<CheckFailure> {
  try {
    await promise
  } catch (error) {
    if (error instanceof CheckFailure) return error
    throw error
  }
  throw new Error('expected a CheckFailure')
}

const fast = { intervalMs: 0, timeoutMs: 60_000 }

describe('runCheck', () => {
  test('reports progress, then the upload, then returns the finished job', async () => {
    const events: string[] = []
    const job = await runCheck(
      source(accept, [{ job_id: 'j', status: 'processing' }, done]),
      file,
      {
        ...fast,
        onUploadProgress: (f) => events.push(`progress ${f}`),
        onUploaded: () => events.push('uploaded'),
      },
    )
    expect(job.verdict).toBe('no_violation')
    expect(events).toEqual(['progress 0.5', 'progress 1', 'uploaded'])
  })

  test('a rejected upload fails on the upload step', async () => {
    const reject: JobSource['upload'] = async () => {
      throw new JobError('bad_file')
    }
    const failure = await failureOf(
      runCheck(source(reject, [done]), file, {
        ...fast,
        onUploadProgress() {},
        onUploaded() {},
      }),
    )
    expect([failure.step, failure.kind]).toEqual(['upload', 'bad_file'])
  })

  test('a failed job fails on the analysis step', async () => {
    const failure = await failureOf(
      runCheck(source(accept, [{ job_id: 'j', status: 'failed' }]), file, {
        ...fast,
        onUploadProgress() {},
        onUploaded() {},
      }),
    )
    expect([failure.step, failure.kind]).toEqual(['analysis', 'failed'])
  })

  test('a reply in the wrong shape is a bad_response', async () => {
    const half: JobResponse = {
      job_id: 'j',
      status: 'done',
      verdict: null,
      violations: null,
    }
    const failure = await failureOf(
      runCheck(source(accept, [half]), file, {
        ...fast,
        onUploadProgress() {},
        onUploaded() {},
      }),
    )
    expect([failure.step, failure.kind]).toEqual(['analysis', 'bad_response'])
  })

  test('an unexpected error still becomes a CheckFailure', async () => {
    const broken: JobSource['upload'] = async () => {
      throw new TypeError('boom')
    }
    const failure = await failureOf(
      runCheck(source(broken, [done]), file, {
        ...fast,
        onUploadProgress() {},
        onUploaded() {},
      }),
    )
    expect([failure.step, failure.kind]).toEqual(['upload', 'failed'])
  })

  test('passes the caller signal to the upload and every poll', async () => {
    const controller = new AbortController()
    const seen: (AbortSignal | undefined)[] = []
    const watched: JobSource = {
      upload: async (_file, _onProgress, signal) => {
        seen.push(signal)
        return { job_id: 'j' }
      },
      getJob: async (_jobId, signal) => {
        seen.push(signal)
        return done
      },
    }
    await runCheck(watched, file, {
      ...fast,
      signal: controller.signal,
      onUploadProgress() {},
      onUploaded() {},
    })
    expect(seen).toEqual([controller.signal, controller.signal])
  })
})

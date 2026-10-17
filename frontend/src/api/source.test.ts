import { describe, expect, test } from 'bun:test'
import { createFixtureSource, FIXTURE_TYPE } from './fixtureSource'
import { parseJobResponse } from './parse'
import { pollJob } from './poll'
import { JobError, type JobSource } from './source'
import type { JobResponse } from './types'

function clock(start = 0) {
  let t = start
  return {
    now: () => t,
    advance: (ms: number) => (t += ms),
    sleep: async (ms: number) => void (t += ms),
  }
}

function fakeFile(name: string): File {
  return new File([new Uint8Array([1, 2, 3])], name)
}

const capture = async (_file: File, times: readonly number[]) => ({
  duration: 14.7,
  frames: times.map((time) => ({
    time: Math.max(0, time),
    base64: `frame-${time}`,
  })),
})

describe('fixture source', () => {
  test('upload reports progress up to 1 and returns only a job_id', async () => {
    const c = clock()
    const source = createFixtureSource({
      capture,
      uploadMs: 100,
      sleep: c.sleep,
      now: c.now,
    })
    const seen: number[] = []
    const response = await source.upload(fakeFile('Х-17.mov'), (f) =>
      seen.push(f),
    )
    expect(Object.keys(response)).toEqual(['job_id'])
    expect(seen[0]).toBe(0)
    expect(seen.at(-1)).toBe(1)
  })

  test('processing, then a violation at the labelled second with 3 frames', async () => {
    const c = clock()
    const source = createFixtureSource({
      capture,
      analyzeMs: 3000,
      uploadMs: 0,
      sleep: c.sleep,
      now: c.now,
    })
    const { job_id } = await source.upload(fakeFile('Х-17.mov'), () => {})
    expect((await source.getJob(job_id)).status).toBe('processing')
    c.advance(3000)
    const job = parseJobResponse(await source.getJob(job_id))
    expect(job.verdict).toBe('violation')
    const [violation] = job.violations ?? []
    expect(violation?.type).toBe(FIXTURE_TYPE)
    expect(violation?.timecode_sec).toBe(7)
    expect(violation?.evidence_frames.map((f) => f.timestamp_sec)).toEqual([
      6.4, 7, 7.6,
    ])
  })

  test('clean, unknown and "fail" files', async () => {
    const c = clock()
    const source = createFixtureSource({
      capture,
      analyzeMs: 0,
      uploadMs: 0,
      sleep: c.sleep,
      now: c.now,
    })
    const result = async (name: string) =>
      source.getJob((await source.upload(fakeFile(name), () => {})).job_id)
    expect(await result('Х-3.mov')).toMatchObject({
      status: 'done',
      verdict: 'no_violation',
      violations: [],
    })
    expect(await result('other.mov')).toMatchObject({
      status: 'done',
      verdict: 'no_violation',
    })
    expect(await result('fail-test.mov')).toMatchObject({ status: 'failed' })
  })

  test('a frame capture error becomes a failed job, not a crash', async () => {
    const c = clock()
    const source = createFixtureSource({
      capture: async () => {
        throw new Error('cannot decode')
      },
      analyzeMs: 0,
      uploadMs: 0,
      sleep: c.sleep,
      now: c.now,
    })
    const { job_id } = await source.upload(fakeFile('Х-17.mov'), () => {})
    expect((await source.getJob(job_id)).status).toBe('failed')
  })

  test('unknown job id is not_found', async () => {
    const source = createFixtureSource({ capture })
    await expect(source.getJob('nope')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})

function scripted(
  responses: (JobResponse | JobError)[],
): JobSource & { calls: number } {
  const source = {
    calls: 0,
    upload: async () => ({ job_id: 'j' }),
    getJob: async () => {
      const next = responses[Math.min(source.calls, responses.length - 1)]!
      source.calls += 1
      if (next instanceof JobError) throw next
      return next
    },
  }
  return source
}

const processing: JobResponse = { job_id: 'j', status: 'processing' }
const done: JobResponse = {
  job_id: 'j',
  status: 'done',
  verdict: 'no_violation',
  violations: [],
}

describe('pollJob', () => {
  test('stops on done', async () => {
    const c = clock()
    const source = scripted([processing, processing, done])
    const job = await pollJob(source, 'j', {
      intervalMs: 1000,
      timeoutMs: 60_000,
      now: c.now,
      sleep: c.sleep,
    })
    expect(job.status).toBe('done')
    expect(source.calls).toBe(3)
  })

  test('returns failed jobs to the caller', async () => {
    const c = clock()
    const job = await pollJob(
      scripted([{ job_id: 'j', status: 'failed' }]),
      'j',
      {
        intervalMs: 1000,
        timeoutMs: 60_000,
        now: c.now,
        sleep: c.sleep,
      },
    )
    expect(job.status).toBe('failed')
  })

  test('gives up after the timeout', async () => {
    const c = clock()
    const promise = pollJob(scripted([processing]), 'j', {
      intervalMs: 2000,
      timeoutMs: 300_000,
      now: c.now,
      sleep: c.sleep,
    })
    await expect(promise).rejects.toMatchObject({ kind: 'timeout' })
  })

  test('rides out a few network errors, then fails', async () => {
    const c = clock()
    const flaky = scripted([
      new JobError('network'),
      new JobError('server'),
      done,
    ])
    expect(
      (
        await pollJob(flaky, 'j', {
          intervalMs: 1,
          timeoutMs: 60_000,
          now: c.now,
          sleep: c.sleep,
        })
      ).status,
    ).toBe('done')

    const down = scripted([new JobError('network')])
    await expect(
      pollJob(down, 'j', {
        intervalMs: 1,
        timeoutMs: 60_000,
        maxTransientErrors: 3,
        now: c.now,
        sleep: c.sleep,
      }),
    ).rejects.toMatchObject({ kind: 'network' })
  })

  test('does not retry a 401 or 404', async () => {
    const c = clock()
    const source = scripted([new JobError('unauthorized')])
    await expect(
      pollJob(source, 'j', {
        intervalMs: 1,
        timeoutMs: 60_000,
        now: c.now,
        sleep: c.sleep,
      }),
    ).rejects.toMatchObject({ kind: 'unauthorized' })
  })
})

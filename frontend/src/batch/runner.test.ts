import { describe, expect, test } from 'bun:test'
import { JobError, type JobSource } from '@/api/source'
import type { DoneJob, JobResponse } from '@/api/types'
import type { PickedVideo } from '@/video'
import { createBatchRunner, type BatchRunner } from './runner'
import type { BatchState } from './types'

type Reply = JobResponse | JobError

const done = (jobId: string): JobResponse => ({
  job_id: jobId,
  status: 'done',
  verdict: 'no_violation',
  violations: [],
})

const processing = (jobId: string): JobResponse => ({
  job_id: jobId,
  status: 'processing',
})

class FakeServer implements JobSource {
  log: string[] = []
  active = 0
  maxActive = 0
  uploadErrors = new Map<string, JobError[]>()
  replies = new Map<string, Reply[]>()
  gates = new Map<string, () => void>()
  heldFiles = new Set<string>()
  honorAbort = true
  private jobs = 0

  hold(fileName: string) {
    this.heldFiles.add(fileName)
  }

  release(fileName: string) {
    this.heldFiles.delete(fileName)
    this.gates.get(fileName)?.()
  }

  answer(jobId: string, ...replies: Reply[]) {
    this.replies.set(jobId, replies)
  }

  failUpload(fileName: string, ...errors: JobError[]) {
    this.uploadErrors.set(fileName, errors)
  }

  async upload(
    file: File,
    onProgress: (fraction: number) => void,
    signal?: AbortSignal,
  ) {
    this.enter()
    try {
      this.log.push(`upload ${file.name}`)
      onProgress(0.5)
      await this.waitFor(file.name, signal)
      const error = this.uploadErrors.get(file.name)?.shift()
      if (error) throw error
      onProgress(1)
      this.jobs += 1
      return { job_id: `job-${this.jobs}` }
    } finally {
      this.leave()
    }
  }

  async getJob(jobId: string) {
    this.enter()
    try {
      this.log.push(`poll ${jobId}`)
      await Bun.sleep(0)
      const replies = this.replies.get(jobId) ?? [done(jobId)]
      const reply = replies.length > 1 ? replies.shift()! : replies[0]!
      if (reply instanceof JobError) throw reply
      return reply
    } finally {
      this.leave()
    }
  }

  private waitFor(fileName: string, signal?: AbortSignal) {
    if (!this.heldFiles.has(fileName)) return Bun.sleep(0)
    return new Promise<void>((resolve, reject) => {
      this.gates.set(fileName, resolve)
      if (this.honorAbort) {
        signal?.addEventListener('abort', () => reject(new JobError('aborted')))
      }
    })
  }

  private enter() {
    this.active += 1
    this.maxActive = Math.max(this.maxActive, this.active)
  }

  private leave() {
    this.active -= 1
  }
}

function setup(
  timeoutMs = 60_000,
  extra: Partial<Parameters<typeof createBatchRunner>[0]> = {},
) {
  const server = new FakeServer()
  const revoked: string[] = []
  let posterCalls = 0
  let postersActive = 0
  let postersMax = 0
  const runner = createBatchRunner({
    source: server,
    intervalMs: 0,
    timeoutMs,
    now: () => 1000,
    ...extra,
    pickVideo: (file): PickedVideo => ({
      file,
      url: `blob:${file.name}`,
      posterUrl: null,
      duration: null,
    }),
    withPoster: async (video) => {
      posterCalls += 1
      postersActive += 1
      postersMax = Math.max(postersMax, postersActive)
      await Bun.sleep(1)
      postersActive -= 1
      return { ...video, posterUrl: `poster:${video.file.name}` }
    },
    revokeVideo: (video) => revoked.push(video.url),
  })
  return {
    server,
    runner,
    revoked,
    posters: () => ({ calls: posterCalls, max: postersMax }),
  }
}

const file = (name: string) => new File([new Uint8Array([1])], name)

const files = (...names: string[]) => names.map(file)

function stages(state: BatchState): string[] {
  return state.items.map(({ video, stage }) => {
    const name = video.file.name
    if (stage.kind === 'failed') return `${name}: ${stage.error}`
    return `${name}: ${stage.kind}`
  })
}

async function until(
  runner: BatchRunner,
  ready: (state: BatchState) => boolean,
) {
  for (let attempt = 0; attempt < 500; attempt += 1) {
    if (ready(runner.getState())) return
    await Bun.sleep(1)
  }
  throw new Error(`still waiting: ${stages(runner.getState()).join(', ')}`)
}

const settled = (state: BatchState) =>
  state.items.length > 0 &&
  state.items.every(
    ({ stage }) =>
      stage.kind === 'done' ||
      stage.kind === 'failed' ||
      (stage.kind === 'queued' && state.pausedBy !== null),
  )

const idOf = (runner: BatchRunner, name: string) =>
  runner.getState().items.find((item) => item.video.file.name === name)!.id

describe('batch runner', () => {
  test('checks videos one by one and uploads the next only after a result', async () => {
    const { server, runner } = setup()
    server.answer(
      'job-1',
      processing('job-1'),
      processing('job-1'),
      done('job-1'),
    )
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, settled)

    expect(stages(runner.getState())).toEqual(['a.mov: done', 'b.mov: done'])
    expect(server.log).toEqual([
      'upload a.mov',
      'poll job-1',
      'poll job-1',
      'poll job-1',
      'upload b.mov',
      'poll job-2',
    ])
    expect(server.maxActive).toBe(1)
  })

  test('a problem with one file does not stop the others', async () => {
    const { server, runner } = setup()
    server.failUpload('b.mov', new JobError('bad_file'))
    runner.start(files('a.mov', 'b.mov', 'c.mov'), [])
    await until(runner, settled)

    expect(stages(runner.getState())).toEqual([
      'a.mov: done',
      'b.mov: bad_file',
      'c.mov: done',
    ])
    expect(runner.getState().pausedBy).toBeNull()
  })

  test('no connection pauses the queue and retry resumes it', async () => {
    const { server, runner } = setup()
    server.failUpload('b.mov', new JobError('network'))
    runner.start(files('a.mov', 'b.mov', 'c.mov'), [])
    await until(runner, settled)

    expect(stages(runner.getState())).toEqual([
      'a.mov: done',
      'b.mov: network',
      'c.mov: queued',
    ])
    expect(runner.getState().pausedBy).not.toBeNull()
    expect(server.log).not.toContain('upload c.mov')

    runner.retry(idOf(runner, 'b.mov'))
    await until(runner, (state) => settled(state) && state.pausedBy === null)
    expect(stages(runner.getState())).toEqual([
      'a.mov: done',
      'b.mov: done',
      'c.mov: done',
    ])
  })

  test('a rejected key stops the queue without sending more files', async () => {
    const { server, runner } = setup()
    server.failUpload('a.mov', new JobError('unauthorized'))
    runner.start(files('a.mov', 'b.mov', 'c.mov'), [])
    await until(runner, settled)

    expect(stages(runner.getState())).toEqual([
      'a.mov: unauthorized',
      'b.mov: queued',
      'c.mov: queued',
    ])
    expect(server.log).toEqual(['upload a.mov'])
  })

  test('after a timeout retry polls the same job instead of uploading again', async () => {
    const { server, runner } = setup(0)
    server.answer('job-1', processing('job-1'))
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, settled)

    expect(stages(runner.getState())).toEqual([
      'a.mov: timeout',
      'b.mov: queued',
    ])
    expect(server.log).toEqual(['upload a.mov', 'poll job-1'])

    server.answer('job-1', done('job-1'))
    runner.retry(idOf(runner, 'a.mov'))
    await until(runner, (state) => settled(state) && state.pausedBy === null)

    expect(stages(runner.getState())).toEqual(['a.mov: done', 'b.mov: done'])
    expect(server.log).toEqual([
      'upload a.mov',
      'poll job-1',
      'poll job-1',
      'upload b.mov',
      'poll job-2',
    ])
  })

  test('if the server lost the job, retry uploads the file again in the same attempt', async () => {
    const { server, runner } = setup()
    const offline = Array.from({ length: 6 }, () => new JobError('network'))
    server.answer('job-1', ...offline)
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, settled)
    expect(stages(runner.getState())).toEqual([
      'a.mov: network',
      'b.mov: queued',
    ])

    server.answer('job-1', { job_id: 'job-1', status: 'failed' })
    runner.retry(idOf(runner, 'a.mov'))
    await until(runner, (state) => settled(state) && state.pausedBy === null)

    expect(stages(runner.getState())).toEqual(['a.mov: done', 'b.mov: done'])
    expect(server.log.filter((entry) => entry === 'upload a.mov')).toHaveLength(
      2,
    )
  })

  test('a late answer from a stopped check does not start a second queue', async () => {
    const { server, runner } = setup()
    server.honorAbort = false
    server.hold('a.mov')
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, (state) => state.items[0]?.stage.kind === 'uploading')

    runner.reset()
    server.hold('d.mov')
    server.failUpload('c.mov', new JobError('bad_file'))
    runner.start(files('c.mov', 'd.mov', 'e.mov'), [])
    await until(runner, (state) => state.items[1]?.stage.kind === 'uploading')

    server.release('a.mov')
    await Bun.sleep(5)
    runner.retry(idOf(runner, 'c.mov'))
    await Bun.sleep(5)
    const uploadsOf = (name: string) =>
      server.log.filter((entry) => entry === `upload ${name}`).length
    expect(uploadsOf('c.mov')).toBe(1)

    server.release('d.mov')
    await until(runner, settled)
    expect(stages(runner.getState())).toEqual([
      'c.mov: done',
      'd.mov: done',
      'e.mov: done',
    ])
    expect(uploadsOf('c.mov')).toBe(2)
    expect(uploadsOf('b.mov')).toBe(0)
  })

  test('a retry while the queue runs does not start a second queue', async () => {
    const { server, runner } = setup()
    server.failUpload('a.mov', new JobError('bad_file'))
    server.hold('b.mov')
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, (state) => state.items[1]?.stage.kind === 'uploading')

    runner.retry(idOf(runner, 'a.mov'))
    await Bun.sleep(5)
    expect(server.active).toBe(1)
    server.release('b.mov')
    await until(runner, settled)

    expect(stages(runner.getState())).toEqual(['a.mov: done', 'b.mov: done'])
    expect(server.maxActive).toBe(1)
  })

  test('stopping cancels the upload in progress', async () => {
    const { server, runner } = setup()
    server.hold('a.mov')
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, (state) => state.items[0]?.stage.kind === 'uploading')

    runner.reset()
    await Bun.sleep(1)
    expect(server.active).toBe(0)

    runner.start(files('c.mov'), [])
    await until(runner, settled)
    expect(stages(runner.getState())).toEqual(['c.mov: done'])
    expect(server.maxActive).toBe(1)
    expect(server.log).toEqual(['upload a.mov', 'upload c.mov', 'poll job-1'])
  })

  test('while paused, a retry of another row waits for the row that paused the queue', async () => {
    const { server, runner } = setup(0)
    server.failUpload('a.mov', new JobError('bad_file'))
    server.answer('job-1', processing('job-1'))
    runner.start(files('a.mov', 'b.mov', 'c.mov'), [])
    await until(runner, settled)
    expect(stages(runner.getState())).toEqual([
      'a.mov: bad_file',
      'b.mov: timeout',
      'c.mov: queued',
    ])

    runner.retry(idOf(runner, 'a.mov'))
    await Bun.sleep(5)
    expect(stages(runner.getState())[0]).toBe('a.mov: queued')
    expect(server.log).toEqual(['upload a.mov', 'upload b.mov', 'poll job-1'])

    server.answer('job-1', done('job-1'))
    runner.retry(idOf(runner, 'b.mov'))
    await until(runner, (state) => settled(state) && state.pausedBy === null)
    expect(stages(runner.getState())).toEqual([
      'a.mov: done',
      'b.mov: done',
      'c.mov: done',
    ])
    expect(server.log.slice(3)).toEqual([
      'poll job-1',
      'upload a.mov',
      'poll job-2',
      'upload c.mov',
      'poll job-3',
    ])
  })

  test('results after a stop are ignored and every video link is released', async () => {
    const { server, runner, revoked } = setup()
    server.honorAbort = false
    server.hold('a.mov')
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, (state) => state.items[0]?.stage.kind === 'uploading')

    runner.reset()
    server.release('a.mov')
    await Bun.sleep(5)

    expect(runner.getState().items).toEqual([])
    expect(revoked).toEqual(['blob:a.mov', 'blob:b.mov'])
    expect(server.log).toEqual(['upload a.mov'])
  })

  test('posters load one at a time', async () => {
    const { runner, posters } = setup()
    runner.start(files('a.mov', 'b.mov', 'c.mov'), [])
    await until(runner, (state) =>
      state.items.every((item) => item.video.posterUrl !== null),
    )
    expect(posters()).toEqual({ calls: 3, max: 1 })
  })

  test('opens a finished report and goes back to the list', async () => {
    const { runner } = setup()
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, settled)
    const id = idOf(runner, 'b.mov')
    runner.open(id)
    expect(runner.getState().openId).toBe(id)
    runner.close()
    expect(runner.getState()).toMatchObject({ openId: null, lastOpenedId: id })
  })

  test('a file already in history is done at once and skips the server', async () => {
    const saved: JobResponse = done('old-job')
    const finished: string[] = []
    const { server, runner } = setup(60_000, {
      findSaved: async (file) =>
        file.name === 'b.mov' ? { job: saved as DoneJob, checkedAt: 5 } : null,
      onDone: (item) => finished.push(item.video.file.name),
    })
    runner.start(files('a.mov', 'b.mov'), [])
    await until(runner, settled)
    expect(stages(runner.getState())).toEqual(['a.mov: done', 'b.mov: done'])
    expect(server.log).toEqual(['upload a.mov', 'poll job-1'])
    expect(finished).toEqual(['a.mov'])
  })
})

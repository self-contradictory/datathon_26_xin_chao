import { sleep as wait } from '@/utils/async'
import { JobError, type JobSource } from './source'
import type { JobResponse } from './types'

export interface PollOptions {
  intervalMs: number
  timeoutMs: number
  maxTransientErrors?: number
  signal?: AbortSignal
  now?: () => number
  sleep?: (ms: number) => Promise<void>
}

export async function pollJob(
  source: JobSource,
  jobId: string,
  {
    intervalMs,
    timeoutMs,
    maxTransientErrors = 5,
    signal,
    now = () => Date.now(),
    sleep = wait,
  }: PollOptions,
): Promise<JobResponse> {
  const startedAt = now()
  let transientErrors = 0

  for (;;) {
    if (signal?.aborted) throw new JobError('aborted')
    try {
      const job = await source.getJob(jobId, signal)
      transientErrors = 0
      if (job.status !== 'processing') return job
    } catch (error) {
      const transient =
        error instanceof JobError &&
        (error.kind === 'network' || error.kind === 'server')
      if (!transient) throw error
      transientErrors += 1
      if (transientErrors > maxTransientErrors) throw error
    }
    if (now() - startedAt >= timeoutMs) throw new JobError('timeout')
    await sleep(intervalMs)
  }
}

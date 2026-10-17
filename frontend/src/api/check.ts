import type { ProcessingStep } from '@/screens/contracts'
import { pollJob } from './poll'
import { JobError, type JobErrorKind, type JobSource } from './source'
import { isDone, type DoneJob } from './types'

export class CheckFailure extends Error {
  readonly kind: JobErrorKind
  readonly step: ProcessingStep

  constructor(kind: JobErrorKind, step: ProcessingStep) {
    super(`${step}: ${kind}`)
    this.name = 'CheckFailure'
    this.kind = kind
    this.step = step
  }
}

export interface CheckOptions {
  intervalMs: number
  timeoutMs: number
  signal?: AbortSignal
  onUploadProgress: (fraction: number) => void
  onUploaded: () => void
}

export async function runCheck(
  source: JobSource,
  file: File,
  { intervalMs, timeoutMs, signal, onUploadProgress, onUploaded }: CheckOptions,
): Promise<DoneJob> {
  let step: ProcessingStep = 'upload'
  try {
    const { job_id } = await source.upload(file, onUploadProgress, signal)
    step = 'analysis'
    onUploaded()
    const job = await pollJob(source, job_id, {
      intervalMs,
      timeoutMs,
      signal,
    })
    if (job.status === 'failed') throw new JobError('failed')
    if (!isDone(job)) throw new JobError('bad_response')
    return job
  } catch (error) {
    const kind = error instanceof JobError ? error.kind : 'failed'
    throw new CheckFailure(kind, step)
  }
}

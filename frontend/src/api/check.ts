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

export interface UploadOptions {
  signal?: AbortSignal
  onUploadProgress: (fraction: number) => void
}

export interface WaitOptions {
  intervalMs: number
  timeoutMs: number
  signal?: AbortSignal
}

export interface CheckOptions extends UploadOptions, WaitOptions {
  onUploaded: () => void
}

export type PollingOptions = Omit<WaitOptions, 'signal'>

export function asCheckFailure(error: unknown): CheckFailure {
  return error instanceof CheckFailure
    ? error
    : new CheckFailure('failed', 'analysis')
}

function failureAt(step: ProcessingStep, error: unknown): CheckFailure {
  const kind = error instanceof JobError ? error.kind : 'failed'
  return new CheckFailure(kind, step)
}

export async function uploadVideo(
  source: JobSource,
  file: File,
  { signal, onUploadProgress }: UploadOptions,
): Promise<string> {
  try {
    const { job_id } = await source.upload(file, onUploadProgress, signal)
    return job_id
  } catch (error) {
    throw failureAt('upload', error)
  }
}

export async function waitForJob(
  source: JobSource,
  jobId: string,
  { intervalMs, timeoutMs, signal }: WaitOptions,
): Promise<DoneJob> {
  try {
    const job = await pollJob(source, jobId, { intervalMs, timeoutMs, signal })
    if (job.status === 'failed') throw new JobError('failed')
    if (!isDone(job)) throw new JobError('bad_response')
    return job
  } catch (error) {
    throw failureAt('analysis', error)
  }
}

export async function runCheck(
  source: JobSource,
  file: File,
  { intervalMs, timeoutMs, signal, onUploadProgress, onUploaded }: CheckOptions,
): Promise<DoneJob> {
  const jobId = await uploadVideo(source, file, { signal, onUploadProgress })
  onUploaded()
  return waitForJob(source, jobId, { intervalMs, timeoutMs, signal })
}

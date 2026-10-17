import type { AnalyzeResponse, JobResponse } from './types'

export interface JobSource {
  upload(
    file: File,
    onProgress: (fraction: number) => void,
  ): Promise<AnalyzeResponse>
  getJob(jobId: string): Promise<JobResponse>
}

export type JobErrorKind =
  | 'network'
  | 'unauthorized'
  | 'not_found'
  | 'bad_file'
  | 'server'
  | 'bad_response'
  | 'timeout'
  | 'failed'

export class JobError extends Error {
  readonly kind: JobErrorKind

  constructor(kind: JobErrorKind, message: string = kind) {
    super(message)
    this.name = 'JobError'
    this.kind = kind
  }
}

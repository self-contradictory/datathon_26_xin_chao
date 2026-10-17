import type { JobResponse } from '@/api/types'

export type ReviewDecision = 'confirmed' | 'rejected'

export interface ReviewMark {
  decision: ReviewDecision
  at: number
}

export type Review = Record<number, ReviewMark>

export interface CheckRecord {
  jobId: string
  fileName: string
  fileSize: number
  fileHash: string | null
  createdAt: number
  result: JobResponse
  review: Review
  poster?: string | null
  duration?: number | null
  hasVideo?: boolean
  video?: Blob
}

export interface CheckStore {
  get(jobId: string): Promise<CheckRecord | undefined>
  findByHash(hash: string): Promise<CheckRecord | undefined>
  put(record: CheckRecord): Promise<void>
  list(): Promise<CheckRecord[]>
  remove(jobId: string): Promise<void>
  clear(): Promise<void>
}

export function mergeRecord(
  previous: CheckRecord | undefined,
  record: CheckRecord,
): CheckRecord {
  return {
    ...previous,
    ...record,
    fileHash: record.fileHash ?? previous?.fileHash ?? null,
    poster: record.poster ?? previous?.poster ?? null,
    duration: record.duration ?? previous?.duration ?? null,
  }
}

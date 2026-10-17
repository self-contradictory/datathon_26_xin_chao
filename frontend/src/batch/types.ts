import type { JobErrorKind } from '@/api/source'
import type { DoneJob } from '@/api/types'
import type { ProcessingStep } from '@/screens/contracts'
import type { RejectedFile } from '@/utils/file'
import type { PickedVideo } from '@/video'

export type BatchStage =
  | { kind: 'queued'; jobId: string | null }
  | { kind: 'uploading'; progress: number }
  | { kind: 'analyzing'; jobId: string }
  | { kind: 'done'; job: DoneJob; checkedAt: number }
  | {
      kind: 'failed'
      error: JobErrorKind
      step: ProcessingStep
      jobId: string | null
    }

export interface BatchItem {
  id: string
  video: PickedVideo
  stage: BatchStage
}

export interface BatchState {
  items: BatchItem[]
  rejected: RejectedFile[]
  paused: boolean
  openId: string | null
  lastOpenedId: string | null
}

export interface BatchCounts {
  total: number
  finished: number
  violations: number
  clean: number
  failed: number
}

export type BatchAction =
  | { type: 'start'; items: BatchItem[]; rejected: RejectedFile[] }
  | { type: 'reset' }
  | { type: 'poster'; id: string; video: PickedVideo }
  | { type: 'uploading'; id: string; progress: number }
  | { type: 'analyzing'; id: string; jobId: string }
  | { type: 'done'; id: string; job: DoneJob; checkedAt: number }
  | {
      type: 'failed'
      id: string
      error: JobErrorKind
      step: ProcessingStep
      jobId: string | null
    }
  | { type: 'retry'; id: string }
  | { type: 'open'; id: string }
  | { type: 'close' }

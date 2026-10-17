import type { JobErrorKind } from '@/api/source'
import type { DoneJob } from '@/api/types'
import type { BatchStage } from '@/batch/types'
import type { RejectedFile } from '@/utils/file'

export interface UploadScreenProps {
  onSubmit: (file: File) => void
  onSubmitMany: (files: File[], rejected: RejectedFile[]) => void
  focusTitle?: boolean
  preview?:
    | { state: 'dragover'; fileName: string; fileSize: number }
    | { state: 'error'; fileName: string }
    | { state: 'too_many'; count: number }
}

export type ProcessingStep = 'upload' | 'analysis'

export type ProcessingPhase = 'uploading' | 'analyzing' | 'failed'

export interface ProcessingScreenProps {
  fileName: string
  fileSize: number
  duration: number | null
  posterUrl: string | null
  phase: ProcessingPhase
  uploadProgress: number
  startedAt: number
  stoppedAt: number | null
  error: JobErrorKind | null
  failedStep: ProcessingStep | null
  onRetry: () => void
  onNewVideo: () => void
}

export interface ReportScreenProps {
  job: DoneJob
  fileName: string
  fileSize: number | null
  duration: number | null
  videoUrl: string | null
  posterUrl: string | null
  checkedAt: number
  file: File | null
  exit: ReportExit
}

export interface ReportExit {
  kind: 'newVideo' | 'backToList'
  onClick: () => void
}

export interface BatchRowView {
  id: string
  fileName: string
  fileSize: number
  duration: number | null
  posterUrl: string | null
  stage: BatchStage
}

export interface BatchScreenProps {
  rows: BatchRowView[]
  rejected: RejectedFile[]
  pausedBy: string | null
  returnFocusId: string | null
  onOpen: (id: string) => void
  onRetry: (id: string) => void
  onStartOver: () => void
}

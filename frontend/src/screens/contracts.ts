import type { JobErrorKind } from '@/api/source'
import type { DoneJob } from '@/api/types'

export interface UploadScreenProps {
  onSubmit: (file: File) => void
  preview?:
    | { state: 'dragover'; fileName: string; fileSize: number }
    | { state: 'error'; fileName: string }
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
  onNewVideo: () => void
}

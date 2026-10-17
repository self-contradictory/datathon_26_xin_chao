import type { ProcessingScreenProps, ProcessingStep } from '@/screens/contracts'

export type StepKey = ProcessingStep
export type StepState = 'done' | 'active' | 'error' | 'pending'

export const STEPS: readonly StepKey[] = ['upload', 'analysis']

export function stepStates(
  phase: ProcessingScreenProps['phase'],
  failedStep: StepKey | null,
): Record<StepKey, StepState> {
  const current =
    phase === 'uploading'
      ? 'upload'
      : phase === 'analyzing'
        ? 'analysis'
        : (failedStep ?? 'analysis')
  const currentIndex = STEPS.indexOf(current)
  const stateAt = (index: number): StepState =>
    index < currentIndex
      ? 'done'
      : index > currentIndex
        ? 'pending'
        : phase === 'failed'
          ? 'error'
          : 'active'
  return { upload: stateAt(0), analysis: stateAt(1) }
}

export function uploadPercent(uploadProgress: number): number {
  if (!Number.isFinite(uploadProgress)) return 0
  return Math.min(100, Math.max(0, Math.floor(uploadProgress * 100)))
}

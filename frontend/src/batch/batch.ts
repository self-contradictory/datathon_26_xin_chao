import type { JobErrorKind } from '@/api/source'
import { showsViolations } from '@/api/types'
import type {
  BatchAction,
  BatchCounts,
  BatchItem,
  BatchStage,
  BatchState,
} from './types'

export const EMPTY_BATCH: BatchState = {
  items: [],
  rejected: [],
  paused: false,
  openId: null,
  lastOpenedId: null,
}

const PAUSING_ERRORS: ReadonlySet<JobErrorKind> = new Set([
  'network',
  'unauthorized',
  'timeout',
  'server',
])

const POLL_AGAIN_ERRORS: ReadonlySet<JobErrorKind> = new Set([
  'network',
  'timeout',
  'server',
])

export function pausesQueue(error: JobErrorKind): boolean {
  return PAUSING_ERRORS.has(error)
}

export function retryStage(
  stage: Extract<BatchStage, { kind: 'failed' }>,
): Extract<BatchStage, { kind: 'queued' }> {
  const pollAgain =
    stage.step === 'analysis' && POLL_AGAIN_ERRORS.has(stage.error)
  return { kind: 'queued', jobId: pollAgain ? stage.jobId : null }
}

export function isQueued(item: BatchItem): boolean {
  return item.stage.kind === 'queued'
}

export function isUnfinished({ stage }: Pick<BatchItem, 'stage'>): boolean {
  const { kind } = stage
  return kind === 'queued' || kind === 'uploading' || kind === 'analyzing'
}

export function nextQueued(items: readonly BatchItem[]): BatchItem | undefined {
  return items.find(isQueued)
}

export function batchCounts(
  items: readonly Pick<BatchItem, 'stage'>[],
): BatchCounts {
  let violations = 0
  let clean = 0
  let failed = 0
  for (const { stage } of items) {
    if (stage.kind === 'failed') failed += 1
    if (stage.kind !== 'done') continue
    if (showsViolations(stage.job)) violations += 1
    else clean += 1
  }
  return {
    total: items.length,
    finished: violations + clean + failed,
    violations,
    clean,
    failed,
  }
}

function findItem(state: BatchState, id: string): BatchItem | undefined {
  return state.items.find((item) => item.id === id)
}

function updateItem(
  state: BatchState,
  id: string,
  change: (item: BatchItem) => BatchItem,
): BatchState {
  if (!findItem(state, id)) return state
  return {
    ...state,
    items: state.items.map((item) => (item.id === id ? change(item) : item)),
  }
}

function setStage(state: BatchState, id: string, stage: BatchStage) {
  return updateItem(state, id, (item) => ({ ...item, stage }))
}

export function batchReducer(
  state: BatchState,
  action: BatchAction,
): BatchState {
  switch (action.type) {
    case 'start':
      return { ...EMPTY_BATCH, items: action.items, rejected: action.rejected }
    case 'reset':
      return EMPTY_BATCH
    case 'poster':
      return updateItem(state, action.id, (item) => ({
        ...item,
        video: action.video,
      }))
    case 'uploading':
      return setStage(state, action.id, {
        kind: 'uploading',
        progress: action.progress,
      })
    case 'analyzing':
      return setStage(state, action.id, {
        kind: 'analyzing',
        jobId: action.jobId,
      })
    case 'done':
      return setStage(state, action.id, {
        kind: 'done',
        job: action.job,
        checkedAt: action.checkedAt,
      })
    case 'failed': {
      const next = setStage(state, action.id, {
        kind: 'failed',
        error: action.error,
        step: action.step,
        jobId: action.jobId,
      })
      if (next === state) return state
      return {
        ...next,
        paused: pausesQueue(action.error) && next.items.some(isQueued),
      }
    }
    case 'retry': {
      const stage = findItem(state, action.id)?.stage
      if (stage?.kind !== 'failed') return state
      return {
        ...setStage(state, action.id, retryStage(stage)),
        paused: false,
      }
    }
    case 'open':
      if (findItem(state, action.id)?.stage.kind !== 'done') return state
      return { ...state, openId: action.id, lastOpenedId: action.id }
    case 'close':
      return { ...state, openId: null }
  }
}

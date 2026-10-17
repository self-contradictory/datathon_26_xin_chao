import { describe, expect, test } from 'bun:test'
import type { JobErrorKind } from '@/api/source'
import type { DoneJob } from '@/api/types'
import type { PickedVideo } from '@/video'
import {
  batchCounts,
  batchReducer,
  EMPTY_BATCH,
  nextQueued,
  pausesQueue,
  retryStage,
} from './batch'
import type { BatchItem, BatchStage, BatchState } from './types'

const clean: DoneJob = {
  job_id: 'j1',
  status: 'done',
  verdict: 'no_violation',
  violations: [],
}

const flagged: DoneJob = {
  job_id: 'j2',
  status: 'done',
  verdict: 'violation',
  violations: [
    {
      type: 'Наличные вне зоны видимости камеры',
      timecode_sec: 7,
      description: 'Кассир убрал деньги под стол.',
      evidence_frames: [{ timestamp_sec: 7, image_base64: 'AAAA' }],
    },
  ],
}

function video(name: string): PickedVideo {
  return {
    file: new File([new Uint8Array([1])], name),
    url: `blob:${name}`,
    posterUrl: null,
    duration: null,
  }
}

function item(id: string, stage: BatchStage): BatchItem {
  return { id, video: video(`${id}.mov`), stage }
}

const queued: BatchStage = { kind: 'queued', jobId: null }

function batchOf(...items: BatchItem[]): BatchState {
  return batchReducer(EMPTY_BATCH, { type: 'start', items, rejected: [] })
}

function stageOf(state: BatchState, id: string) {
  return state.items.find((entry) => entry.id === id)?.stage
}

describe('batch reducer', () => {
  test('start replaces everything and reset empties the batch', () => {
    const state = batchOf(item('a', queued))
    expect(state.items.map((entry) => entry.id)).toEqual(['a'])
    expect(batchReducer(state, { type: 'reset' })).toBe(EMPTY_BATCH)
  })

  test('moves a video through upload, analysis and result', () => {
    let state = batchOf(item('a', queued))
    state = batchReducer(state, { type: 'uploading', id: 'a', progress: 0.4 })
    expect(stageOf(state, 'a')).toEqual({ kind: 'uploading', progress: 0.4 })
    state = batchReducer(state, { type: 'analyzing', id: 'a', jobId: 'j1' })
    expect(stageOf(state, 'a')).toEqual({ kind: 'analyzing', jobId: 'j1' })
    state = batchReducer(state, {
      type: 'done',
      id: 'a',
      job: clean,
      checkedAt: 5,
    })
    expect(stageOf(state, 'a')).toEqual({
      kind: 'done',
      job: clean,
      checkedAt: 5,
    })
  })

  test('an action for an unknown video changes nothing', () => {
    const state = batchOf(item('a', queued))
    expect(
      batchReducer(state, { type: 'uploading', id: 'x', progress: 1 }),
    ).toBe(state)
    expect(
      batchReducer(state, {
        type: 'failed',
        id: 'x',
        error: 'network',
        step: 'upload',
        jobId: null,
      }),
    ).toBe(state)
  })

  test('a pausing error pauses only while videos still wait', () => {
    const waiting = batchReducer(
      batchOf(item('a', queued), item('b', queued)),
      {
        type: 'failed',
        id: 'a',
        error: 'network',
        step: 'upload',
        jobId: null,
      },
    )
    expect(waiting.pausedBy).toBe('a')

    const last = batchReducer(batchOf(item('a', queued)), {
      type: 'failed',
      id: 'a',
      error: 'network',
      step: 'upload',
      jobId: null,
    })
    expect(last.pausedBy).toBeNull()

    const fileError = batchReducer(
      batchOf(item('a', queued), item('b', queued)),
      {
        type: 'failed',
        id: 'a',
        error: 'bad_file',
        step: 'upload',
        jobId: null,
      },
    )
    expect(fileError.pausedBy).toBeNull()
  })

  test('retry queues only a failed video', () => {
    const state = batchOf(item('a', queued), item('b', queued))
    expect(batchReducer(state, { type: 'retry', id: 'a' })).toBe(state)
  })

  test('only a retry of the video that paused the queue lifts the pause', () => {
    let state = batchOf(
      item('a', {
        kind: 'failed',
        error: 'bad_file',
        step: 'upload',
        jobId: null,
      }),
      item('b', queued),
      item('c', queued),
    )
    state = batchReducer(state, {
      type: 'failed',
      id: 'b',
      error: 'timeout',
      step: 'analysis',
      jobId: 'j1',
    })
    expect(state.pausedBy).toBe('b')

    state = batchReducer(state, { type: 'retry', id: 'a' })
    expect(stageOf(state, 'a')).toEqual(queued)
    expect(state.pausedBy).toBe('b')

    state = batchReducer(state, { type: 'retry', id: 'b' })
    expect(stageOf(state, 'b')).toEqual({ kind: 'queued', jobId: 'j1' })
    expect(state.pausedBy).toBeNull()
  })

  test('open works only for a finished video and close keeps the last one', () => {
    let state = batchOf(
      item('a', { kind: 'done', job: clean, checkedAt: 1 }),
      item('b', queued),
    )
    expect(batchReducer(state, { type: 'open', id: 'b' })).toBe(state)
    state = batchReducer(state, { type: 'open', id: 'a' })
    expect([state.openId, state.lastOpenedId]).toEqual(['a', 'a'])
    state = batchReducer(state, { type: 'close' })
    expect([state.openId, state.lastOpenedId]).toEqual([null, 'a'])
  })

  test('a new poster keeps the stage', () => {
    const state = batchReducer(batchOf(item('a', queued)), {
      type: 'poster',
      id: 'a',
      video: { ...video('a.mov'), posterUrl: 'data:poster', duration: 12 },
    })
    expect(state.items[0]!.video.posterUrl).toBe('data:poster')
    expect(state.items[0]!.stage).toEqual(queued)
  })
})

describe('batch helpers', () => {
  test('pausesQueue stops only on errors that repeat for every video', () => {
    const pausing: JobErrorKind[] = [
      'network',
      'unauthorized',
      'timeout',
      'server',
    ]
    const fileOnly: JobErrorKind[] = [
      'bad_file',
      'failed',
      'not_found',
      'bad_response',
    ]
    expect(pausing.every(pausesQueue)).toBe(true)
    expect(fileOnly.some(pausesQueue)).toBe(false)
  })

  test('retryStage polls the same job only when it may still be running', () => {
    const failed = (
      error: 'timeout' | 'network' | 'server' | 'failed' | 'bad_file',
      step: 'upload' | 'analysis',
    ) => ({ kind: 'failed' as const, error, step, jobId: 'j1' })

    expect(retryStage(failed('timeout', 'analysis'))).toEqual({
      kind: 'queued',
      jobId: 'j1',
    })
    expect(retryStage(failed('network', 'analysis')).jobId).toBe('j1')
    expect(retryStage(failed('server', 'analysis')).jobId).toBe('j1')
    expect(retryStage(failed('failed', 'analysis')).jobId).toBeNull()
    expect(retryStage(failed('network', 'upload')).jobId).toBeNull()
    expect(retryStage(failed('bad_file', 'upload')).jobId).toBeNull()
  })

  test('nextQueued keeps the list order', () => {
    const items = [
      item('a', { kind: 'done', job: clean, checkedAt: 1 }),
      item('b', queued),
      item('c', queued),
    ]
    expect(nextQueued(items)?.id).toBe('b')
    expect(nextQueued([items[0]!])).toBeUndefined()
  })

  test('nextQueued finishes a job the server already has before new uploads', () => {
    const items = [item('a', queued), item('b', { kind: 'queued', jobId: 'j' })]
    expect(nextQueued(items)?.id).toBe('b')
  })

  test('batchCounts counts errors as finished and the rest as unfinished', () => {
    const counts = batchCounts([
      item('a', { kind: 'done', job: clean, checkedAt: 1 }),
      item('b', { kind: 'done', job: flagged, checkedAt: 1 }),
      item('c', {
        kind: 'failed',
        error: 'bad_file',
        step: 'upload',
        jobId: null,
      }),
      item('d', { kind: 'uploading', progress: 0.5 }),
      item('e', queued),
    ])
    expect(counts).toEqual({
      total: 5,
      finished: 3,
      violations: 1,
      clean: 1,
      failed: 1,
      unfinished: 2,
    })
  })
})

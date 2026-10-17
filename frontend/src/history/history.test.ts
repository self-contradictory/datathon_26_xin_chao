import { describe, expect, test } from 'bun:test'
import type { JobResponse } from '@/api/types'
import { sha256Hex } from './hash'
import { pickVideosToEvict } from './evict'
import { createMemoryStore } from './memoryStore'
import { openCheckStore } from './store'
import { mergeRecord, type CheckRecord } from './types'

const result: JobResponse = {
  job_id: 'j1',
  status: 'done',
  verdict: 'no_violation',
  violations: [],
}

function record(jobId: string, createdAt: number): CheckRecord {
  return {
    jobId,
    fileName: `${jobId}.mov`,
    fileSize: 10,
    fileHash: null,
    createdAt,
    result: { ...result, job_id: jobId },
    review: {},
  }
}

describe('check store', () => {
  test('puts, gets and replaces a record by job id', async () => {
    const store = createMemoryStore()
    expect(await store.get('j1')).toBeUndefined()
    await store.put(record('j1', 1))
    await store.put({
      ...record('j1', 1),
      review: { 0: { decision: 'confirmed', at: 5 } },
    })
    expect((await store.get('j1'))?.review[0]?.decision).toBe('confirmed')
    expect(await store.list()).toHaveLength(1)
  })

  test('lists newest first, removes and clears', async () => {
    const store = createMemoryStore()
    await store.put(record('old', 1))
    await store.put(record('new', 2))
    expect((await store.list()).map((r) => r.jobId)).toEqual(['new', 'old'])
    await store.remove('new')
    expect((await store.list()).map((r) => r.jobId)).toEqual(['old'])
    await store.clear()
    expect(await store.list()).toEqual([])
  })
})

describe('history helpers', () => {
  test('mergeRecord keeps poster, duration and hash a bare write lacks', () => {
    const full = {
      ...record('j', 1),
      fileHash: 'h',
      poster: 'p',
      duration: 12,
    }
    const bare = { ...record('j', 1), fileHash: null }
    expect(mergeRecord(full, bare)).toMatchObject({
      fileHash: 'h',
      poster: 'p',
      duration: 12,
    })
  })

  test('sha256Hex hashes the file bytes', async () => {
    expect(await sha256Hex(new Blob(['abc']))).toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })
})

describe('history storage', () => {
  test('finds the newest record with the same file hash', async () => {
    const store = createMemoryStore()
    await store.put({ ...record('old', 1), fileHash: 'h' })
    await store.put({ ...record('new', 2), fileHash: 'h' })
    await store.put({ ...record('other', 3), fileHash: 'x' })
    expect((await store.findByHash('h'))?.jobId).toBe('new')
    expect(await store.findByHash('none')).toBeUndefined()
  })

  test('keeps the video when a later update has none', async () => {
    const store = createMemoryStore()
    await store.put({ ...record('j', 1), video: new Blob(['v']) })
    await store.put({ ...record('j', 1), review: {} })
    expect((await store.get('j'))?.hasVideo).toBe(true)
    expect((await store.list())[0]).not.toHaveProperty('video')
  })

  test('falls back to memory when IndexedDB cannot open', async () => {
    const store = await openCheckStore(async () => {
      throw new Error('blocked')
    })
    await store.put(record('j', 1))
    expect((await store.get('j'))?.jobId).toBe('j')
  })

  test('pickVideosToEvict drops the oldest videos over the limit', () => {
    const at = (jobId: string, createdAt: number, fileSize: number) => ({
      jobId,
      createdAt,
      fileSize,
      hasVideo: true,
    })
    expect(
      pickVideosToEvict([at('a', 1, 40), at('b', 2, 40), at('c', 3, 40)], 100),
    ).toEqual(['a'])
    expect(pickVideosToEvict([at('a', 1, 40)], 100)).toEqual([])
    expect(
      pickVideosToEvict([{ ...at('a', 1, 400), hasVideo: false }], 100),
    ).toEqual([])
    expect(pickVideosToEvict([at('a', 1, 40), at('b', 2, 400)], 100)).toEqual([
      'a',
    ])
  })
})

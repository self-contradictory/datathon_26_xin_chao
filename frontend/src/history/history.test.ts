import { describe, expect, test } from 'bun:test'
import type { JobResponse } from '@/api/types'
import { sha256Hex } from './hash'
import { createMemoryStore } from './memoryStore'
import { violationKey, type CheckRecord } from './types'

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
  test('violationKey joins the job id and the index', () => {
    expect(violationKey('abc', 2)).toBe('abc:2')
  })

  test('sha256Hex hashes the file bytes', async () => {
    expect(await sha256Hex(new Blob(['abc']))).toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })
})

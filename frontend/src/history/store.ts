import { createIdbStore, openDatabase } from './idbStore'
import { createMemoryStore } from './memoryStore'
import type { CheckStore } from './types'

export async function openCheckStore(
  open: () => Promise<IDBDatabase> = openDatabase,
): Promise<CheckStore> {
  if (typeof indexedDB === 'undefined') return createMemoryStore()
  try {
    return createIdbStore(await open())
  } catch {
    return createMemoryStore()
  }
}

function lazyStore(): CheckStore {
  let ready: Promise<CheckStore> | null = null
  const store = () => (ready ??= openCheckStore())
  return {
    get: async (jobId) => (await store()).get(jobId),
    findByHash: async (hash) => (await store()).findByHash(hash),
    put: async (record) => (await store()).put(record),
    list: async () => (await store()).list(),
    remove: async (jobId) => (await store()).remove(jobId),
    clear: async () => (await store()).clear(),
  }
}

export const checkStore: CheckStore = lazyStore()

export async function keepStorage(): Promise<void> {
  try {
    await navigator.storage?.persist?.()
  } catch {
    return
  }
}

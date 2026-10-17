import type { CheckRecord, CheckStore } from './types'

export function createMemoryStore(): CheckStore {
  const records = new Map<string, CheckRecord>()

  return {
    async get(jobId) {
      return records.get(jobId)
    },
    async put(record) {
      records.set(record.jobId, record)
    },
    async list() {
      return [...records.values()].sort((a, b) => b.createdAt - a.createdAt)
    },
    async remove(jobId) {
      records.delete(jobId)
    },
    async clear() {
      records.clear()
    },
  }
}

export const checkStore: CheckStore = createMemoryStore()

import type { CheckRecord, CheckStore } from './types'

export function createMemoryStore(): CheckStore {
  const records = new Map<string, CheckRecord>()

  return {
    async get(jobId) {
      return records.get(jobId)
    },
    async findByHash(hash) {
      return [...records.values()]
        .filter((record) => record.fileHash === hash)
        .sort((a, b) => b.createdAt - a.createdAt)[0]
    },
    async put(record) {
      const video = record.video ?? records.get(record.jobId)?.video
      records.set(record.jobId, {
        ...record,
        video,
        hasVideo: video !== undefined,
      })
    },
    async list() {
      return [...records.values()]
        .map(({ video: _video, ...rest }) => rest)
        .sort((a, b) => b.createdAt - a.createdAt)
    },
    async remove(jobId) {
      records.delete(jobId)
    },
    async clear() {
      records.clear()
    },
  }
}

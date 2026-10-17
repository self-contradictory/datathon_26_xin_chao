import { USE_FIXTURES } from '@/config'
import { pickVideosToEvict, VIDEO_LIMIT_BYTES } from './evict'
import { mergeRecord, type CheckRecord, type CheckStore } from './types'

const DB_NAME = USE_FIXTURES ? 'forte-checks-demo' : 'forte-checks'
const CHECKS = 'checks'
const VIDEOS = 'videos'

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function done(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error)
  })
}

export function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open(DB_NAME, 1)
    open.onupgradeneeded = () => {
      const db = open.result
      const checks = db.createObjectStore(CHECKS, { keyPath: 'jobId' })
      checks.createIndex('createdAt', 'createdAt')
      checks.createIndex('fileHash', 'fileHash')
      db.createObjectStore(VIDEOS)
    }
    open.onsuccess = () => resolve(open.result)
    open.onerror = () => reject(open.error)
  })
}

export function createIdbStore(db: IDBDatabase): CheckStore {
  async function all(): Promise<CheckRecord[]> {
    const tx = db.transaction(CHECKS, 'readonly')
    return request(tx.objectStore(CHECKS).getAll() as IDBRequest<CheckRecord[]>)
  }

  async function evictVideos() {
    const evict = pickVideosToEvict(await all(), VIDEO_LIMIT_BYTES)
    if (evict.length === 0) return
    const tx = db.transaction([CHECKS, VIDEOS], 'readwrite')
    const checks = tx.objectStore(CHECKS)
    for (const jobId of evict) {
      tx.objectStore(VIDEOS).delete(jobId)
      const record = await request(
        checks.get(jobId) as IDBRequest<CheckRecord | undefined>,
      )
      if (record) checks.put({ ...record, hasVideo: false })
    }
    await done(tx)
  }

  async function write(record: CheckRecord, video: Blob | undefined) {
    const tx = db.transaction([CHECKS, VIDEOS], 'readwrite')
    const previous = await request(
      tx.objectStore(CHECKS).get(record.jobId) as IDBRequest<
        CheckRecord | undefined
      >,
    )
    const hasVideo = video !== undefined || previous?.hasVideo === true
    tx.objectStore(CHECKS).put({ ...mergeRecord(previous, record), hasVideo })
    if (video) tx.objectStore(VIDEOS).put(video, record.jobId)
    await done(tx)
  }

  return {
    async get(jobId) {
      const tx = db.transaction([CHECKS, VIDEOS], 'readonly')
      const record = await request(
        tx.objectStore(CHECKS).get(jobId) as IDBRequest<
          CheckRecord | undefined
        >,
      )
      if (!record?.hasVideo) return record
      const video = await request(
        tx.objectStore(VIDEOS).get(jobId) as IDBRequest<Blob | undefined>,
      )
      return video ? { ...record, video } : { ...record, hasVideo: false }
    },
    async findByHash(hash) {
      const tx = db.transaction(CHECKS, 'readonly')
      const found = await request(
        tx.objectStore(CHECKS).index('fileHash').getAll(hash) as IDBRequest<
          CheckRecord[]
        >,
      )
      return found.sort((a, b) => b.createdAt - a.createdAt)[0]
    },
    async put({ video, ...record }) {
      try {
        await write(record, video)
      } catch (error) {
        if (!video) throw error
        await write(record, undefined)
        return
      }
      if (video) await evictVideos()
    },
    async list() {
      return (await all()).sort((a, b) => b.createdAt - a.createdAt)
    },
    async remove(jobId) {
      const tx = db.transaction([CHECKS, VIDEOS], 'readwrite')
      tx.objectStore(CHECKS).delete(jobId)
      tx.objectStore(VIDEOS).delete(jobId)
      await done(tx)
    },
    async clear() {
      const tx = db.transaction([CHECKS, VIDEOS], 'readwrite')
      tx.objectStore(CHECKS).clear()
      tx.objectStore(VIDEOS).clear()
      await done(tx)
    },
  }
}

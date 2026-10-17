import type { DoneJob } from '@/api/types'
import { sha256Hex } from './hash'
import { checkStore, keepStorage } from './store'
import type { CheckRecord } from './types'

export async function saveCheck({
  job,
  file,
  checkedAt,
  poster,
  duration,
}: {
  job: DoneJob
  file: File
  checkedAt: number
  poster: string | null
  duration: number | null
}): Promise<void> {
  const fileHash = await sha256Hex(file)
  const saved = await checkStore.get(job.job_id)
  await checkStore.put({
    jobId: job.job_id,
    fileName: file.name,
    fileSize: file.size,
    fileHash,
    createdAt: saved?.createdAt ?? checkedAt,
    result: job,
    review: saved?.review ?? {},
    poster,
    duration,
    video: file,
  })
  void keepStorage()
}

export async function findSaved(file: File): Promise<CheckRecord | undefined> {
  const hash = await sha256Hex(file)
  return hash ? checkStore.findByHash(hash) : undefined
}

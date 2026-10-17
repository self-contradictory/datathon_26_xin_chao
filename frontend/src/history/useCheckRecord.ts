import { useEffect, useEffectEvent, useState } from 'react'
import type { DoneJob } from '@/api/types'
import { sha256Hex } from './hash'
import { checkStore } from './store'
import type { CheckRecord, Review, ReviewDecision } from './types'

export interface CheckSource {
  job: DoneJob
  fileName: string
  fileSize: number | null
  checkedAt: number
  file: File | null
}

export function useCheckRecord({
  job,
  fileName,
  fileSize,
  checkedAt,
  file,
}: CheckSource) {
  const jobId = job.job_id
  const [record, setRecord] = useState<CheckRecord | null>(null)

  const ensureRecord = useEffectEvent(
    async (saved: CheckRecord | undefined): Promise<CheckRecord> => {
      if (saved) return saved
      const fresh: CheckRecord = {
        jobId,
        fileName,
        fileSize: fileSize ?? 0,
        fileHash: null,
        createdAt: checkedAt,
        result: job,
        review: {},
      }
      await checkStore.put(fresh)
      return fresh
    },
  )

  const addHash = useEffectEvent(
    async (base: CheckRecord): Promise<CheckRecord | null> => {
      if (base.fileHash || !file) return null
      const fileHash = await sha256Hex(file)
      if (!fileHash) return null
      const latest = (await checkStore.get(jobId)) ?? base
      const hashed = { ...latest, fileHash }
      await checkStore.put(hashed)
      return hashed
    },
  )

  useEffect(() => {
    let live = true
    checkStore
      .get(jobId)
      .then(ensureRecord)
      .then((base) => {
        if (live) setRecord(base)
        return addHash(base)
      })
      .then((hashed) => {
        if (live && hashed)
          setRecord((prev) =>
            prev ? { ...prev, fileHash: hashed.fileHash } : hashed,
          )
      })
      .catch(() => {})
    return () => {
      live = false
    }
  }, [jobId])

  async function decide(index: number, decision: ReviewDecision | null) {
    const latest = await checkStore.get(jobId)
    if (!latest) return
    const review: Review = { ...latest.review }
    if (decision) review[index] = { decision, at: Date.now() }
    else delete review[index]
    const { video: _video, ...rest } = latest
    const updated = { ...rest, review }
    await checkStore.put(updated)
    setRecord(updated)
  }

  return { record, review: record?.review ?? {}, decide }
}

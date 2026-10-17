import type { CheckRecord } from './types'

export const VIDEO_LIMIT_BYTES = 1024 ** 3

export function pickVideosToEvict(
  records: readonly Pick<
    CheckRecord,
    'jobId' | 'fileSize' | 'createdAt' | 'hasVideo'
  >[],
  limitBytes: number,
): string[] {
  let kept = 0
  const evict: string[] = []
  const newestFirst = records
    .filter((record) => record.hasVideo)
    .sort((a, b) => b.createdAt - a.createdAt)
  for (const record of newestFirst) {
    if (kept === 0 || kept + record.fileSize <= limitBytes)
      kept += record.fileSize
    else evict.push(record.jobId)
  }
  return evict
}

import type { Violation } from '@/api/types'

const ACTIVE_WINDOW_SEC = 3
export const SEEK_LEAD_SEC = 2

export function activeViolationIndex(
  violations: readonly Pick<Violation, 'timecode_sec'>[],
  time: number,
): number | null {
  let best: number | null = null
  let bestDistance = Infinity
  violations.forEach(({ timecode_sec }, index) => {
    const distance = Math.abs(timecode_sec - time)
    if (distance <= ACTIVE_WINDOW_SEC && distance < bestDistance) {
      best = index
      bestDistance = distance
    }
  })
  return best
}

export function playheadIndex(
  violations: readonly Pick<Violation, 'timecode_sec'>[],
  time: number,
  pinned: number | null,
): number | null {
  const chosen = pinned === null ? undefined : violations[pinned]
  if (
    chosen &&
    time >= chosen.timecode_sec - SEEK_LEAD_SEC - 0.5 &&
    time <= chosen.timecode_sec + ACTIVE_WINDOW_SEC
  )
    return pinned
  return activeViolationIndex(violations, time)
}

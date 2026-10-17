import type { Violation } from '@/api/types'

export const ACTIVE_WINDOW_SEC = 3

export function activeViolationIndex(
  violations: readonly Pick<Violation, 'timecode_sec'>[],
  time: number,
  window = ACTIVE_WINDOW_SEC,
): number | null {
  let best: number | null = null
  let bestDistance = Infinity
  violations.forEach(({ timecode_sec }, index) => {
    const distance = Math.abs(timecode_sec - time)
    if (distance <= window && distance < bestDistance) {
      best = index
      bestDistance = distance
    }
  })
  return best
}

export function stepIndex(index: number, by: 1 | -1, count: number): number {
  return (index + by + count) % count
}

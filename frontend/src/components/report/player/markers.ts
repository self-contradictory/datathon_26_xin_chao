import type { PlayerMarker } from './types'

const MERGE_PX = 24
const TOOLTIP_HALF_PX = 120

export interface MarkerGroup {
  first: PlayerMarker
  items: PlayerMarker[]
  ratio: number
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function groupMarkers(
  markers: readonly PlayerMarker[],
  span: number,
  trackWidth: number,
): MarkerGroup[] {
  if (span <= 0) return []
  const groups: MarkerGroup[] = []
  for (const marker of [...markers].sort((a, b) => a.time - b.time)) {
    const ratio = clamp(marker.time / span, 0, 1)
    const last = groups.at(-1)
    const overlapsLast =
      last !== undefined &&
      trackWidth > 0 &&
      (ratio - last.ratio) * trackWidth < MERGE_PX
    if (overlapsLast) last.items.push(marker)
    else groups.push({ first: marker, items: [marker], ratio })
  }
  return groups
}

export function fallbackSpan(markers: readonly PlayerMarker[]): number {
  const latest = Math.max(0, ...markers.map((marker) => marker.time))
  return latest > 0 ? latest / 0.8 : 0
}

export type TooltipAlign = 'start' | 'center' | 'end'

export function tooltipAlign(ratio: number, trackWidth: number): TooltipAlign {
  const fromLeft = ratio * trackWidth
  if (fromLeft < TOOLTIP_HALF_PX) return 'start'
  if (trackWidth - fromLeft < TOOLTIP_HALF_PX) return 'end'
  return 'center'
}

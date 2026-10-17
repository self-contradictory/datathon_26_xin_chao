import type { Ref } from 'react'

export interface PlayerMarker {
  id: string
  position: number
  time: number
  label: string
  dimmed?: boolean
}

export interface SeekOptions {
  lead?: number
  pause?: boolean
}

export interface PlayerHandle {
  seek(time: number, options?: SeekOptions): void
  pause(): void
}

export interface PlayerProps {
  src: string | null
  posterUrl: string | null
  duration: number | null
  markers: readonly PlayerMarker[]
  activeMarkerId: string | null
  onMarkerSelect: (id: string) => void
  onTimeChange?: (time: number) => void
  ref?: Ref<PlayerHandle>
}

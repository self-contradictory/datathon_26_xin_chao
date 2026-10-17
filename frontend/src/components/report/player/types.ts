import type { Ref } from 'react'

export interface PlayerMarker {
  id: string
  time: number
  label: string
}

export interface PlayerHandle {
  seek(time: number): void
  pause(): void
}

export interface PlayerProps {
  src: string | null
  posterUrl: string | null
  duration: number | null
  markers: readonly PlayerMarker[]
  activeMarkerId: string | null
  onMarkerSelect: (id: string) => void
  ref?: Ref<PlayerHandle>
}

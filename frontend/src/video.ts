import { captureFrames, jpegDataUrl } from '@/utils/frames'

export interface PickedVideo {
  file: File
  url: string
  posterUrl: string | null
  duration: number | null
}

export function pickVideo(file: File): PickedVideo {
  return {
    file,
    url: URL.createObjectURL(file),
    posterUrl: null,
    duration: null,
  }
}

export async function withPoster(video: PickedVideo): Promise<PickedVideo> {
  const { duration, frames } = await captureFrames(video.url, [0])
  return {
    ...video,
    duration: duration || null,
    posterUrl: frames[0] ? jpegDataUrl(frames[0].base64) : null,
  }
}

export function revokeVideo(video: PickedVideo): void {
  URL.revokeObjectURL(video.url)
}

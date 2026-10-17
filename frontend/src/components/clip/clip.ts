import { baseName } from '@/utils/file'
export const CLIP_BEFORE_SEC = 2
export const CLIP_AFTER_SEC = 3
export const CLIP_BITRATE = 2_500_000

const MIME_ORDER = [
  { mime: 'video/mp4;codecs=avc1', ext: 'mp4' },
  { mime: 'video/mp4', ext: 'mp4' },
  { mime: 'video/webm;codecs=vp9', ext: 'webm' },
  { mime: 'video/webm', ext: 'webm' },
] as const

export interface RecorderFormat {
  mime: string
  ext: string
}

export function clipWindow(
  time: number,
  duration: number | null,
): { start: number; end: number } {
  const start = Math.max(0, time - CLIP_BEFORE_SEC)
  const limit = duration !== null && duration > 0 ? duration : Infinity
  return { start, end: Math.max(start, Math.min(limit, time + CLIP_AFTER_SEC)) }
}

export function pickRecorderMime(
  isSupported: (mime: string) => boolean,
): RecorderFormat | null {
  return MIME_ORDER.find(({ mime }) => isSupported(mime)) ?? null
}

export function clipFileName(fileName: string, time: string, ext: string) {
  return `${baseName(fileName)}_${time.replace(/:/g, '-')}.${ext}`
}

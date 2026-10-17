export interface CapturedFrame {
  time: number
  base64: string
}

export interface CaptureResult {
  duration: number
  width: number
  height: number
  frames: CapturedFrame[]
}

const TIMEOUT_MS = 15_000

export function once(target: HTMLMediaElement, event: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup()
      reject(new Error(`video: no "${event}" within ${TIMEOUT_MS} ms`))
    }, TIMEOUT_MS)
    const onEvent = () => {
      cleanup()
      resolve()
    }
    const onError = () => {
      cleanup()
      reject(new Error('video: the browser cannot decode this file'))
    }
    function cleanup() {
      clearTimeout(timer)
      target.removeEventListener(event, onEvent)
      target.removeEventListener('error', onError)
    }
    target.addEventListener(event, onEvent)
    target.addEventListener('error', onError)
  })
}

export function clampTime(time: number, duration: number): number {
  const last = Math.max(0, duration - 0.05)
  return Math.min(Math.max(0, time), last)
}

export async function captureFrames(
  src: string,
  times: readonly number[],
  {
    maxWidth = 464,
    quality = 0.82,
  }: { maxWidth?: number; quality?: number } = {},
): Promise<CaptureResult> {
  const video = document.createElement('video')
  video.muted = true
  video.playsInline = true
  video.preload = 'auto'
  video.src = src
  try {
    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA)
      await once(video, 'loadeddata')
    const duration = Number.isFinite(video.duration) ? video.duration : 0
    const scale = Math.min(1, maxWidth / (video.videoWidth || maxWidth))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round((video.videoWidth || maxWidth) * scale)
    canvas.height = Math.round((video.videoHeight || maxWidth) * scale)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('canvas: 2d context is not available')

    const frames: CapturedFrame[] = []
    for (const wanted of times) {
      const time = clampTime(wanted, duration)
      if (Math.abs(video.currentTime - time) > 0.001) {
        const seeked = once(video, 'seeked')
        video.currentTime = time
        await seeked
      }
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
      const dataUrl = canvas.toDataURL('image/jpeg', quality)
      frames.push({ time, base64: dataUrl.slice(dataUrl.indexOf(',') + 1) })
    }
    return {
      duration,
      width: video.videoWidth,
      height: video.videoHeight,
      frames,
    }
  } finally {
    video.removeAttribute('src')
    video.load()
  }
}

export function jpegDataUrl(base64: string): string {
  return `data:image/jpeg;base64,${base64}`
}

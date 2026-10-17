import { once } from '@/utils/frames'
import { clipWindow, CLIP_BITRATE, pickRecorderMime } from './clip'

export interface ClipLabel {
  type: string
  time: string
}

export interface ClipResult {
  blob: Blob
  ext: string
}

const PLATE_HEIGHT = 0.11
const EVENT_BORDER_SEC = 0.5

export function clipFormat() {
  if (typeof MediaRecorder === 'undefined') return null
  if (typeof HTMLCanvasElement.prototype.captureStream !== 'function')
    return null
  return pickRecorderMime((mime) => MediaRecorder.isTypeSupported(mime))
}

export function drawClipFrame(
  context: CanvasRenderingContext2D,
  video: HTMLVideoElement,
  label: ClipLabel,
  eventTime: number,
) {
  const { width, height } = context.canvas
  context.drawImage(video, 0, 0, width, height)
  const plate = Math.round(height * PLATE_HEIGHT)
  const styles = getComputedStyle(document.documentElement)
  context.fillStyle = styles.getPropertyValue('--color-bg').trim()
  context.fillRect(0, height - plate, width, plate)
  context.fillStyle = styles.getPropertyValue('--color-text').trim()
  context.textBaseline = 'middle'
  const size = Math.round(plate * 0.32)
  context.font = `600 ${size}px Rubik, system-ui, sans-serif`
  context.fillText(
    `${label.time} · ${label.type}`,
    Math.round(width * 0.05),
    height - plate / 2,
    width * 0.9,
  )
  if (Math.abs(video.currentTime - eventTime) <= EVENT_BORDER_SEC) {
    const line = Math.max(4, Math.round(width * 0.012))
    context.strokeStyle = styles.getPropertyValue('--color-danger').trim()
    context.lineWidth = line
    context.strokeRect(line / 2, line / 2, width - line, height - line)
  }
}

async function prepare(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  eventTime: number,
) {
  await once(video, 'loadedmetadata')
  const { start, end } = clipWindow(
    eventTime,
    Number.isFinite(video.duration) ? video.duration : null,
  )
  video.currentTime = start
  await once(video, 'seeked')
  canvas.width = video.videoWidth || 464
  canvas.height = video.videoHeight || 848
  const context = canvas.getContext('2d')
  if (!context) throw new Error('clip: no canvas')
  await document.fonts.ready
  return { start, end, context }
}

export async function recordClip(
  videoUrl: string,
  eventTime: number,
  label: ClipLabel,
  onProgress: (fraction: number) => void,
): Promise<ClipResult> {
  const format = clipFormat()
  if (!format) throw new Error('clip: recording is not supported')

  const canvas = document.createElement('canvas')
  const video = document.createElement('video')
  video.muted = true
  video.playsInline = true
  video.preload = 'auto'
  video.src = videoUrl
  const release = () => {
    video.removeAttribute('src')
    video.load()
  }
  const { start, end, context } = await prepare(video, canvas, eventTime).catch(
    (error: unknown) => {
      release()
      throw error
    },
  )

  const stream = canvas.captureStream(30)
  const recorder = new MediaRecorder(stream, {
    mimeType: format.mime,
    videoBitsPerSecond: CLIP_BITRATE,
  })
  const chunks: Blob[] = []
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data)
  }

  const finished = new Promise<void>((resolve) => {
    recorder.onstop = () => resolve()
  })

  let frame = 0
  let stopped = false
  const step = () => {
    if (stopped) return
    drawClipFrame(context, video, label, eventTime)
    onProgress(Math.min(1, (video.currentTime - start) / (end - start || 1)))
    if (video.currentTime >= end || video.ended) {
      stopped = true
      video.pause()
      if (recorder.state !== 'inactive') recorder.stop()
    }
  }
  const loop = () => {
    step()
    if (!stopped) frame = requestAnimationFrame(loop)
  }
  video.addEventListener('timeupdate', step)
  video.addEventListener('ended', step)

  const onVisibility = () => {
    if (document.hidden) {
      video.pause()
      if (recorder.state === 'recording') recorder.pause()
    } else if (recorder.state === 'paused') {
      recorder.resume()
      void video.play()
    }
  }
  document.addEventListener('visibilitychange', onVisibility)

  try {
    drawClipFrame(context, video, label, eventTime)
    recorder.start()
    await video.play()
    loop()
    await finished
  } finally {
    document.removeEventListener('visibilitychange', onVisibility)
    video.removeEventListener('timeupdate', step)
    video.removeEventListener('ended', step)
    cancelAnimationFrame(frame)
    stream.getTracks().forEach((track) => track.stop())
    release()
  }

  return { blob: new Blob(chunks, { type: format.mime }), ext: format.ext }
}

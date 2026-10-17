import { SEEK_LEAD_SEC } from '@/components/report/activeViolation'
import {
  useCallback,
  useEffect,
  useEffectEvent,
  useImperativeHandle,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react'
import { PlayIcon } from '@/components/icons'
import { localeOf, useLang, useStrings } from '@/i18n'
import { formatTime } from '@/utils/time'
import { ControlBar } from './ControlBar'
import { clamp, fallbackSpan } from './markers'
import { Scrubber } from './Scrubber'
import type { PlayerProps } from './types'

export type {
  PlayerHandle,
  PlayerMarker,
  PlayerProps,
  SeekOptions,
} from './types'

const RATES: readonly number[] = [1, 1.5, 2, 0.5]
const PORTRAIT = 9 / 16
const FILL_TOLERANCE = 0.02

export function Player({
  src,
  posterUrl,
  duration,
  markers,
  activeMarkerId,
  onMarkerSelect,
  onTimeChange,
  ref,
}: PlayerProps) {
  const t = useStrings('player')
  const { lang } = useLang()
  const wrapperRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const playButtonRef = useRef<HTMLButtonElement>(null)
  const pendingSeek = useRef<number | null>(null)

  const [current, setCurrent] = useState(0)
  const [mediaDuration, setMediaDuration] = useState<number | null>(null)
  const [aspect, setAspect] = useState(PORTRAIT)
  const [playing, setPlaying] = useState(false)
  const [failed, setFailed] = useState(false)
  const [rate, setRate] = useState(1)
  const [fullscreen, setFullscreen] = useState(false)

  const [loadedSrc, setLoadedSrc] = useState(src)
  if (src !== loadedSrc) {
    setLoadedSrc(src)
    setCurrent(0)
    setMediaDuration(null)
    setAspect(PORTRAIT)
    setPlaying(false)
    setFailed(false)
  }

  const available = src !== null && !failed
  const knownDuration =
    mediaDuration ?? (duration !== null && duration > 0 ? duration : null)
  const span = knownDuration ?? fallbackSpan(markers)
  const totalText = knownDuration !== null ? formatTime(knownDuration) : '--:--'
  const canFullscreen = document.fullscreenEnabled === true
  const fit =
    !fullscreen && Math.abs(aspect - PORTRAIT) < FILL_TOLERANCE
      ? 'object-cover'
      : 'object-contain'

  useEffect(() => {
    if (!playing) return
    let frame = 0
    const tick = () => {
      const video = videoRef.current
      if (video) setCurrent(video.currentTime)
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing])

  const reportTime = useEffectEvent((time: number) => onTimeChange?.(time))
  useEffect(() => reportTime(current), [current])

  useEffect(() => {
    const sync = () =>
      setFullscreen(
        wrapperRef.current !== null &&
          document.fullscreenElement === wrapperRef.current,
      )
    document.addEventListener('fullscreenchange', sync)
    return () => document.removeEventListener('fullscreenchange', sync)
  }, [])

  const seekTo = useCallback(
    (time: number, pause: boolean) => {
      const target = clamp(time, 0, mediaDuration ?? Infinity)
      setCurrent(target)
      const video = videoRef.current
      if (pause) video?.pause()
      if (video && video.readyState >= HTMLMediaElement.HAVE_METADATA)
        video.currentTime = target
      else pendingSeek.current = target
    },
    [mediaDuration],
  )

  useImperativeHandle(
    ref,
    () => ({
      seek: (time, { lead = SEEK_LEAD_SEC, pause = true } = {}) =>
        seekTo(time - lead, pause),
      pause: () => videoRef.current?.pause(),
    }),
    [seekTo],
  )

  function syncDuration() {
    const value = videoRef.current?.duration ?? NaN
    setMediaDuration(Number.isFinite(value) && value > 0 ? value : null)
  }

  function onLoadedMetadata() {
    const video = videoRef.current
    if (!video) return
    video.defaultPlaybackRate = rate
    video.playbackRate = rate
    if (video.videoWidth > 0 && video.videoHeight > 0)
      setAspect(video.videoWidth / video.videoHeight)
    syncDuration()
    if (pendingSeek.current !== null) {
      const limit = Number.isFinite(video.duration) ? video.duration : Infinity
      video.currentTime = clamp(pendingSeek.current, 0, limit)
      pendingSeek.current = null
    }
  }

  function syncTime() {
    const video = videoRef.current
    if (video) setCurrent(video.currentTime)
  }

  function togglePlay() {
    const video = videoRef.current
    if (!video || !available) return
    if (video.paused || video.ended) video.play().catch(() => {})
    else video.pause()
  }

  function cycleRate() {
    const next = RATES[(RATES.indexOf(rate) + 1) % RATES.length] ?? 1
    const video = videoRef.current
    if (video) {
      video.defaultPlaybackRate = next
      video.playbackRate = next
    }
    setRate(next)
  }

  function toggleFullscreen() {
    const wrapper = wrapperRef.current
    if (!wrapper) return
    if (document.fullscreenElement === wrapper)
      document.exitFullscreen().catch(() => {})
    else wrapper.requestFullscreen().catch(() => {})
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!available || event.altKey || event.ctrlKey || event.metaKey) return
    const onButton = event.target instanceof HTMLButtonElement
    if (event.code === 'KeyK' || (event.key === ' ' && !onButton)) {
      event.preventDefault()
      togglePlay()
    }
  }

  const message = src === null ? t.noSource : failed ? t.cannotPlay : null

  return (
    <div
      ref={wrapperRef}
      role="group"
      aria-label={t.player}
      tabIndex={-1}
      onKeyDown={onKeyDown}
      className="@container relative mx-auto aspect-[9/16] w-[min(100%,var(--player-width))] overflow-hidden rounded-md bg-video focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand lg:mx-0 [&:fullscreen]:rounded-none"
    >
      {available ? (
        <video
          ref={videoRef}
          src={src}
          poster={posterUrl ?? undefined}
          preload="metadata"
          playsInline
          aria-hidden="true"
          tabIndex={-1}
          onClick={togglePlay}
          onLoadedMetadata={onLoadedMetadata}
          onDurationChange={syncDuration}
          onTimeUpdate={syncTime}
          onSeeked={syncTime}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          onError={() => {
            setPlaying(false)
            setFailed(true)
          }}
          className={`absolute inset-0 size-full ${fit}`}
        />
      ) : (
        posterUrl && (
          <img
            src={posterUrl}
            alt=""
            className="absolute inset-0 size-full object-contain"
          />
        )
      )}

      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-linear-to-t from-video/70 to-transparent"
      />

      <div
        role="status"
        className={`pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 px-6 pb-[72px] text-center text-white ${
          message ? 'bg-video/60' : ''
        }`}
      >
        {message && (
          <>
            <p className="m-0 text-body font-semibold">{t.unavailable}</p>
            <p className="m-0 text-secondary text-white/80">{message}</p>
          </>
        )}
      </div>

      {available && !playing && (
        <button
          type="button"
          aria-hidden="true"
          tabIndex={-1}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            togglePlay()
            playButtonRef.current?.focus({ preventScroll: true })
          }}
          className="absolute top-[46%] left-1/2 flex size-16 -translate-1/2 cursor-pointer items-center justify-center rounded-full bg-white/92 text-text transition-colors duration-150 hover:bg-white"
        >
          <PlayIcon />
        </button>
      )}

      <div className="absolute inset-x-0 bottom-0 px-2 pb-1 @min-[300px]:px-3">
        <Scrubber
          markers={markers}
          activeMarkerId={activeMarkerId}
          span={span}
          current={current}
          totalText={totalText}
          available={available}
          onSeek={(time) => seekTo(time, false)}
          onMarkerSelect={(marker) => onMarkerSelect(marker.id)}
        />
        {available ? (
          <ControlBar
            playing={playing}
            timeText={`${formatTime(current)} / ${totalText}`}
            rateLabel={`${rate.toLocaleString(localeOf(lang))}×`}
            fullscreen={fullscreen}
            canFullscreen={canFullscreen}
            playButtonRef={playButtonRef}
            onTogglePlay={togglePlay}
            onCycleRate={cycleRate}
            onToggleFullscreen={toggleFullscreen}
          />
        ) : knownDuration !== null ? (
          <p className="m-0 flex h-11 items-center px-1 text-secondary font-medium text-white tabular-nums">
            {totalText}
          </p>
        ) : (
          <div className="h-2" />
        )}
      </div>
    </div>
  )
}

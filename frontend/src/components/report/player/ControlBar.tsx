import type { Ref } from 'react'
import { FullscreenIcon, PauseIcon, PlayIcon } from '@/components/icons'
import { format, useStrings } from '@/i18n'

const BAR_BUTTON =
  'flex h-11 min-w-11 shrink-0 cursor-pointer items-center justify-center rounded-sm text-white transition-colors duration-150 hover:bg-white/10 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-white'

interface ControlBarProps {
  playing: boolean
  timeText: string
  rateLabel: string
  fullscreen: boolean
  canFullscreen: boolean
  playButtonRef: Ref<HTMLButtonElement>
  onTogglePlay: () => void
  onCycleRate: () => void
  onToggleFullscreen: () => void
}

export function ControlBar({
  playing,
  timeText,
  rateLabel,
  fullscreen,
  canFullscreen,
  playButtonRef,
  onTogglePlay,
  onCycleRate,
  onToggleFullscreen,
}: ControlBarProps) {
  const t = useStrings('player')

  return (
    <div className="flex h-11 items-center text-white">
      <button
        ref={playButtonRef}
        type="button"
        aria-label={playing ? t.pause : t.play}
        title={playing ? t.pause : t.play}
        onClick={onTogglePlay}
        className={BAR_BUTTON}
      >
        {playing ? <PauseIcon /> : <PlayIcon />}
      </button>
      <span className="px-1 text-secondary font-medium whitespace-nowrap tabular-nums">
        {timeText}
      </span>
      <span className="flex-1" />
      <button
        type="button"
        aria-label={format(t.speed, { rate: rateLabel })}
        title={format(t.speed, { rate: rateLabel })}
        onClick={onCycleRate}
        className={`${BAR_BUTTON} px-2 text-secondary font-medium tabular-nums`}
      >
        {rateLabel}
      </button>
      {canFullscreen && (
        <button
          type="button"
          aria-label={fullscreen ? t.exitFullscreen : t.fullscreen}
          title={fullscreen ? t.exitFullscreen : t.fullscreen}
          onClick={onToggleFullscreen}
          className={BAR_BUTTON}
        >
          <FullscreenIcon size={20} />
        </button>
      )}
    </div>
  )
}

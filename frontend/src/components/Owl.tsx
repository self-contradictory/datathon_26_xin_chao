import analyzing from '@/assets/owls/analyzing.webp'
import happy from '@/assets/owls/happy.webp'
import idle from '@/assets/owls/idle-still.webp'
import reading from '@/assets/owls/reading.webp'
import warning from '@/assets/owls/warning.webp'

const OWLS = {
  idle: { src: idle, width: 192, height: 206 },
  happy: { src: happy, width: 320, height: 349 },
  warning: { src: warning, width: 480, height: 354 },
  analyzing: { src: analyzing, width: 480, height: 295 },
  reading: { src: reading, width: 480, height: 267 },
}

export type OwlMood = keyof typeof OWLS

export function Owl({
  mood,
  className = '',
}: {
  mood: OwlMood
  className?: string
}) {
  const { src, width, height } = OWLS[mood]
  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      width={width}
      height={height}
      decoding="async"
      className={`block h-auto ${className}`}
    />
  )
}

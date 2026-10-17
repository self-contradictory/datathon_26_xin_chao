import analyzing from '@/assets/owls/analyzing.svg'
import analyzingStill from '@/assets/owls/analyzing-still.webp'
import happy from '@/assets/owls/happy.svg'
import happyStill from '@/assets/owls/happy-still.webp'
import hello from '@/assets/owls/hello.webp'
import idle from '@/assets/owls/idle-still.webp'
import reading from '@/assets/owls/reading.webp'
import warning from '@/assets/owls/warning.svg'
import warningStill from '@/assets/owls/warning-still.webp'

interface OwlImage {
  src: string
  still?: string
  width: number
  height: number
}

const OWLS = {
  idle: { src: idle, width: 192, height: 206 },
  hello: { src: hello, still: idle, width: 192, height: 206 },
  reading: { src: reading, width: 480, height: 267 },
  happy: { src: happy, still: happyStill, width: 640, height: 640 },
  warning: { src: warning, still: warningStill, width: 640, height: 640 },
  analyzing: { src: analyzing, still: analyzingStill, width: 640, height: 640 },
} satisfies Record<string, OwlImage>

export type OwlMood = keyof typeof OWLS

export function Owl({
  mood,
  className = '',
}: {
  mood: OwlMood
  className?: string
}) {
  const { src, width, height, still }: OwlImage = OWLS[mood]
  const image = (
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
  if (!still) return image
  return (
    <picture className="contents">
      <source srcSet={still} media="(prefers-reduced-motion: reduce)" />
      {image}
    </picture>
  )
}

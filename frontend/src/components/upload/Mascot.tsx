import owl from '@/assets/owl.webp'
import owlStill from '@/assets/owl-still.webp'

export function Mascot({ excited }: { excited: boolean }) {
  return (
    <picture
      aria-hidden="true"
      className={`pointer-events-none absolute right-4 bottom-full -mb-1.5 w-24 sm:right-10 sm:w-28 ${
        excited ? 'motion-safe:animate-bounce' : ''
      }`}
    >
      <source srcSet={owlStill} media="(prefers-reduced-motion: reduce)" />
      <img
        src={owl}
        alt=""
        width={192}
        height={206}
        decoding="async"
        className="block h-auto w-full"
      />
    </picture>
  )
}

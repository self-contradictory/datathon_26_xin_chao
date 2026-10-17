import { VideoFileIcon } from '@/components/icons'
import { format, useStrings } from '@/i18n'
import { formatTime } from '@/utils/time'

export function VideoPreview({
  fileName,
  posterUrl,
  duration,
  className = '',
}: {
  fileName: string
  posterUrl: string | null
  duration: number | null
  className?: string
}) {
  const t = useStrings('videoPreview')

  return (
    <figure
      className={`flex w-20 flex-col gap-2 sm:w-28 lg:w-[min(400px,max(200px,calc((100svh-256px)*9/16)))] ${className}`}
    >
      <div className="relative flex aspect-[9/16] w-full items-center justify-center overflow-hidden rounded-sm bg-video lg:rounded-md">
        {posterUrl ? (
          <img
            src={posterUrl}
            alt={format(t.alt, { name: fileName })}
            className="size-full object-cover"
          />
        ) : (
          <VideoFileIcon
            size={24}
            className="size-8 text-text-muted lg:size-12"
            strokeWidth={1.5}
          />
        )}
        {duration !== null && (
          <span
            aria-hidden="true"
            className="absolute right-3 bottom-3 rounded-sm bg-video/70 px-2 text-caption leading-6 font-medium text-white tabular-nums max-lg:hidden"
          >
            {formatTime(duration)}
          </span>
        )}
      </div>
    </figure>
  )
}

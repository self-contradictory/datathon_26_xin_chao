import type { SVGProps } from 'react'

type IconProps = { size?: 20 | 24 } & Omit<
  SVGProps<SVGSVGElement>,
  'width' | 'height'
>

function Stroke({
  size = 24,
  children,
  ...rest
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  )
}

export const UploadIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M12 15V4" />
    <path d="M7.5 8.5L12 4l4.5 4.5" />
    <path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" />
  </Stroke>
)

export const DropIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M12 4v11" />
    <path d="M7.5 10.5L12 15l4.5-4.5" />
    <path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" />
  </Stroke>
)

export const LockIcon = (p: IconProps) => (
  <Stroke {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </Stroke>
)

export const VideoFileIcon = (p: IconProps) => (
  <Stroke {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M10 9.5v5l4-2.5z" />
  </Stroke>
)

export const ErrorIcon = (p: IconProps) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5" />
    <path d="M12 16.5h.01" />
  </Stroke>
)

export const InfoIcon = (p: IconProps) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5" />
    <path d="M12 7.5h.01" />
  </Stroke>
)

export const CheckCircleIcon = (p: IconProps) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8 12.5l2.7 2.7L16 9.5" />
  </Stroke>
)

export const CheckIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Stroke>
)

export const PendingIcon = (p: IconProps) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="9" />
  </Stroke>
)

export const SpinnerIcon = ({
  size = 24,
  className = '',
  ...rest
}: IconProps) => (
  <svg
    aria-hidden="true"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    strokeWidth={2.5}
    strokeLinecap="round"
    className={`animate-spin ${className}`}
    {...rest}
  >
    <circle cx="12" cy="12" r="9" className="stroke-border" />
    <path d="M12 3a9 9 0 0 1 9 9" className="stroke-brand" />
  </svg>
)

export const CloseIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M6 6l12 12" />
    <path d="M18 6L6 18" />
  </Stroke>
)

export const MenuIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
  </Stroke>
)

export const PlusIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </Stroke>
)

export const PlayIcon = ({ size = 24, ...rest }: IconProps) => (
  <svg
    aria-hidden="true"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    {...rest}
  >
    <path d="M8 5.5v13l11-6.5z" fill="currentColor" />
  </svg>
)

export const PauseIcon = ({ size = 24, ...rest }: IconProps) => (
  <svg
    aria-hidden="true"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    {...rest}
  >
    <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" />
  </svg>
)

export const FullscreenIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M4 9V4h5" />
    <path d="M20 9V4h-5" />
    <path d="M4 15v5h5" />
    <path d="M20 15v5h-5" />
  </Stroke>
)

export const ChevronRightIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M9 6l6 6-6 6" />
  </Stroke>
)

export const ChevronLeftIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M15 6l-6 6 6 6" />
  </Stroke>
)

export const ExternalIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M14 4h6v6" />
    <path d="M20 4l-9 9" />
    <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
  </Stroke>
)

export const CopyIcon = (p: IconProps) => (
  <Stroke {...p}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V5a1 1 0 0 1 1-1h10" />
  </Stroke>
)

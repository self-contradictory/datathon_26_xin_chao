export function Toast({ message }: { message: string | null }) {
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4"
    >
      {message && (
        <div className="rounded-md bg-text px-4 py-3 text-secondary text-white shadow-popover">
          {message}
        </div>
      )}
    </div>
  )
}

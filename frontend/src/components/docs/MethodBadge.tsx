export type HttpMethod = 'POST' | 'GET'

const COLORS: Record<HttpMethod, string> = {
  POST: 'bg-text text-white',
  GET: 'border border-border bg-surface text-text',
}

export function MethodBadge({ method }: { method: HttpMethod }) {
  return (
    <span
      className={`rounded-sm px-2 py-0.5 font-mono text-secondary font-medium ${COLORS[method]}`}
    >
      {method}
    </span>
  )
}

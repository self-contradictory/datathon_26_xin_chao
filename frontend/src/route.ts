import { useEffect, useState } from 'react'

export type HashRoute =
  | { page: 'main' }
  | { page: 'rules'; ruleId?: string }
  | { page: 'api' }
  | { page: 'history' }
  | { page: 'check'; jobId: string }
  | { page: 'demo'; state: string }

function decode(value: string): string | null {
  try {
    return decodeURIComponent(value)
  } catch {
    return null
  }
}

export function parseHash(hash: string): HashRoute {
  const path = hash.replace(/^#\/?/, '').replace(/\/+$/, '')
  if (path === 'rules') return { page: 'rules' }
  if (path.startsWith('rules/'))
    return { page: 'rules', ruleId: decode(path.slice(6)) ?? undefined }
  if (path === 'api') return { page: 'api' }
  if (path === 'history') return { page: 'history' }
  if (path.startsWith('check/')) {
    const jobId = decode(path.slice(6))
    return jobId ? { page: 'check', jobId } : { page: 'history' }
  }
  if (path === 'demo' || path.startsWith('demo/'))
    return { page: 'demo', state: path.slice(5) }
  return { page: 'main' }
}

export function useHashRoute(): HashRoute {
  const [route, setRoute] = useState(() => parseHash(window.location.hash))
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

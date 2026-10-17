import { useEffect, useState } from 'react'

export type HashRoute =
  | { page: 'main' }
  | { page: 'rules'; ruleId?: string }
  | { page: 'api' }
  | { page: 'history' }
  | { page: 'check'; jobId: string }
  | { page: 'demo'; state: string }

export function parseHash(hash: string): HashRoute {
  const path = hash.replace(/^#\/?/, '').replace(/\/+$/, '')
  if (path === 'rules') return { page: 'rules' }
  if (path.startsWith('rules/'))
    return { page: 'rules', ruleId: decodeURIComponent(path.slice(6)) }
  if (path === 'api') return { page: 'api' }
  if (path === 'history') return { page: 'history' }
  if (path.startsWith('check/'))
    return { page: 'check', jobId: decodeURIComponent(path.slice(6)) }
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

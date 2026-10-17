import { useEffect, useState } from 'react'

export type HashRoute =
  | { page: 'main' }
  | { page: 'rules' }
  | { page: 'api' }
  | { page: 'demo'; state: string }

export function parseHash(hash: string): HashRoute {
  const path = hash.replace(/^#\/?/, '').replace(/\/+$/, '')
  if (path === 'rules') return { page: 'rules' }
  if (path === 'api') return { page: 'api' }
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

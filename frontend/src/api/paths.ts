export const API_PREFIX = '/api/v1'
export const ANALYZE_PATH = `${API_PREFIX}/analyze`

export function jobPath(jobId: string): string {
  return `${API_PREFIX}/jobs/${encodeURIComponent(jobId)}`
}

export function apiUrl(origin: string, path: string): string {
  return `${origin.replace(/\/+$/, '')}${path}`
}

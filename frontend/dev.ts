import { basename, join } from 'node:path'
import index from './index.html'

const hostname = process.env.HOST ?? '127.0.0.1'
const port = Number(process.env.PORT ?? 3000)
const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000'
const apiKey = process.env.API_KEY ?? ''
const datasetDir = join(import.meta.dir, '..', 'data', 'open', 'videos')

async function proxy(req: Request) {
  const url = new URL(req.url)
  const target = new URL(url.pathname + url.search, apiUrl)
  const headers = new Headers(req.headers)
  if (apiKey && !headers.has('X-API-Key')) headers.set('X-API-Key', apiKey)
  try {
    return await fetch(target, {
      method: req.method,
      headers,
      body: req.body,
      redirect: 'manual',
    })
  } catch {
    return Response.json(
      { detail: `Backend is not reachable at ${apiUrl}` },
      { status: 502 },
    )
  }
}

async function dataset(req: Request) {
  const name = basename(
    decodeURIComponent(new URL(req.url).pathname.slice('/__dataset/'.length)),
  )
  const file = Bun.file(join(datasetDir, name))
  if (!name.toLowerCase().endsWith('.mov') || !(await file.exists())) {
    return new Response('Not found', { status: 404 })
  }
  const headers = {
    'Content-Type': 'video/quicktime',
    'Accept-Ranges': 'bytes',
  }
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.get('range') ?? '')
  if (!range) return new Response(file, { headers })
  const size = file.size
  const start = range[1]
    ? Number(range[1])
    : Math.max(0, size - Number(range[2]))
  const end =
    range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1
  if (start >= size || start > end) {
    return new Response(null, {
      status: 416,
      headers: { 'Content-Range': `bytes */${size}` },
    })
  }
  return new Response(file.slice(start, end + 1), {
    status: 206,
    headers: { ...headers, 'Content-Range': `bytes ${start}-${end}/${size}` },
  })
}

const server = Bun.serve({
  hostname,
  port,
  maxRequestBodySize: 4 * 1024 ** 3,
  routes: {
    '/api/*': proxy,
    '/__dataset/*': dataset,
    '/*': index,
  },
  development: { hmr: true, console: true },
})

console.log(`Frontend: ${server.url}`)
console.log(`API proxy: /api -> ${apiUrl}`)

import { rm } from 'node:fs/promises'
import tailwind from 'bun-plugin-tailwind'

const usesFixtures = process.env.BUN_PUBLIC_DATA_SOURCE === 'fixtures'
const apiOrigin = process.env.BUN_PUBLIC_API_URL ?? ''
const usesVercelProxy = process.env.VERCEL === '1' && !usesFixtures
if (usesVercelProxy) {
  const proxyOrigin = process.env.API_URL ?? ''
  let validOrigin = false
  try {
    const url = new URL(proxyOrigin)
    validOrigin = url.protocol === 'https:' && url.origin === proxyOrigin
  } catch {
    // Report a configuration error without printing environment values.
  }
  if (!validOrigin || !process.env.API_KEY?.startsWith('xc_')) {
    console.error(
      'Set API_URL to the HTTPS backend origin without a trailing slash, and API_KEY to the matching xc_ key in Vercel Environment Variables.',
    )
    process.exit(1)
  }
  if (apiOrigin || process.env.BUN_PUBLIC_API_KEY) {
    console.error(
      'Remove BUN_PUBLIC_API_URL and BUN_PUBLIC_API_KEY from Vercel. Its API proxy uses server-side API_URL and API_KEY.',
    )
    process.exit(1)
  }
} else if (!usesFixtures && !/^https?:\/\/[^/]+\/?$/.test(apiOrigin)) {
  console.error(
    'Set BUN_PUBLIC_API_URL to the backend origin, e.g. https://api.example.kz (without /api/v1), or BUN_PUBLIC_DATA_SOURCE=fixtures.',
  )
  process.exit(1)
}

const outdir = `${import.meta.dir}/dist`
await rm(outdir, { recursive: true, force: true })

const result = await Bun.build({
  entrypoints: [`${import.meta.dir}/index.html`],
  outdir,
  target: 'browser',
  minify: true,
  define: {
    'process.env.NODE_ENV': '"production"',
    ...(usesVercelProxy
      ? {
          'process.env.BUN_PUBLIC_API_URL': '""',
          'process.env.BUN_PUBLIC_API_KEY': '""',
        }
      : {}),
  },
  env: 'BUN_PUBLIC_*',
  plugins: [tailwind],
})

if (!result.success) {
  for (const log of result.logs) console.error(log)
  process.exit(1)
}

console.log('Built frontend to dist/')

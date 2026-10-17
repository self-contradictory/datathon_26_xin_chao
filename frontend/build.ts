import { rm } from 'node:fs/promises'
import tailwind from 'bun-plugin-tailwind'

const usesFixtures = process.env.BUN_PUBLIC_DATA_SOURCE === 'fixtures'
const apiOrigin = process.env.BUN_PUBLIC_API_URL ?? ''
if (!usesFixtures && !/^https?:\/\/[^/]+\/?$/.test(apiOrigin)) {
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
  define: { 'process.env.NODE_ENV': '"production"' },
  env: 'BUN_PUBLIC_*',
  plugins: [tailwind],
})

if (!result.success) {
  for (const log of result.logs) console.error(log)
  process.exit(1)
}

console.log('Built frontend to dist/')

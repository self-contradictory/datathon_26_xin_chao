import { rm } from 'node:fs/promises'
import tailwind from 'bun-plugin-tailwind'

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

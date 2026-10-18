import { expect, test } from 'bun:test'
import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

const frontend = join(import.meta.dir, '..')
const privateKey = 'xc_vercel_build_test_secret'
const privateOrigin = 'https://gpu.example.test'

function build(overrides: Record<string, string> = {}) {
  return Bun.spawnSync([process.execPath, 'run', 'build.ts'], {
    cwd: frontend,
    env: {
      ...process.env,
      VERCEL: '1',
      API_URL: privateOrigin,
      API_KEY: privateKey,
      BUN_PUBLIC_API_URL: '',
      BUN_PUBLIC_API_KEY: '',
      BUN_PUBLIC_DATA_SOURCE: 'api',
      ...overrides,
    },
    stdout: 'pipe',
    stderr: 'pipe',
  })
}

test('Vercel rejects missing credentials and non-origin backend URLs', () => {
  const invalidSettings: Record<string, string>[] = [
    { API_KEY: '' },
    { API_KEY: 'invalid-prefix' },
    { API_URL: '' },
    { API_URL: 'http://gpu.example.test' },
    { API_URL: `${privateOrigin}/api/v1` },
    { API_URL: `${privateOrigin}/` },
  ]
  for (const overrides of invalidSettings) {
    const result = build(overrides)
    expect(result.exitCode).toBe(1)
    expect(result.stderr.toString()).toContain('Set API_URL')
  }
})

test('Vercel rejects browser-visible API credentials', () => {
  const result = build({ BUN_PUBLIC_API_KEY: privateKey })
  expect(result.exitCode).toBe(1)
  expect(result.stderr.toString()).toContain('Remove BUN_PUBLIC_API_URL')
  expect(result.stderr.toString()).not.toContain(privateKey)
})

test('production browser assets contain neither the private API key nor origin', async () => {
  const result = build()
  expect(result.exitCode).toBe(0)
  const dist = join(frontend, 'dist')
  const files = await readdir(dist, { recursive: true, withFileTypes: true })
  expect(files.some((file) => file.isFile() && file.name.endsWith('.js'))).toBe(
    true,
  )
  for (const file of files) {
    if (!file.isFile()) continue
    const contents = await readFile(join(file.parentPath, file.name))
    expect(contents.includes(Buffer.from(privateKey))).toBe(false)
    expect(contents.includes(Buffer.from(privateOrigin))).toBe(false)
  }
})

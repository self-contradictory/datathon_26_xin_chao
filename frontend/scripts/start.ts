import { existsSync } from 'node:fs'
import { join } from 'node:path'
import type { Subprocess } from 'bun'
import {
  BACKEND_DIR,
  BACKEND_URL,
  describeResult,
  ensureDevKey,
  FRONTEND_DIR,
  FRONTEND_URL,
  reachable,
  smokeTest,
  waitFor,
} from './local'

const children: Subprocess[] = []

function stopAll(code = 0): never {
  for (const child of children) child.kill()
  process.exit(code)
}

process.on('SIGINT', () => stopAll())
process.on('SIGTERM', () => stopAll())

async function pipe(stream: ReadableStream<Uint8Array>, label: string) {
  const decoder = new TextDecoder()
  let rest = ''
  for await (const chunk of stream) {
    const lines = (rest + decoder.decode(chunk, { stream: true })).split('\n')
    rest = lines.pop() ?? ''
    for (const line of lines) {
      if (line.trim())
        console.log(`[${label}] ${line.replace(/xc_\w+/g, 'xc_***')}`)
    }
  }
}

function launch(
  label: string,
  cmd: string[],
  cwd: string,
  env: Record<string, string>,
) {
  const child = Bun.spawn(cmd, {
    cwd,
    env: { ...process.env, ...env },
    stdout: 'pipe',
    stderr: 'pipe',
  })
  children.push(child)
  void pipe(child.stdout, label)
  void pipe(child.stderr, label)
  void child.exited.then((code) => {
    if (code !== 0 && code !== null) {
      console.error(`[${label}] stopped with code ${code}`)
      stopAll(1)
    }
  })
}

async function backendStatus(key: string) {
  const reply = await reachable(`${BACKEND_URL}/api/v1/jobs/health-check`, {
    headers: { 'X-API-Key': key },
  })
  if (!reply) return 'down'
  return reply.status === 404 ? 'ours' : 'other'
}

const INSTALL_HELP: Record<string, string> = {
  uv: 'https://docs.astral.sh/uv/getting-started/installation/',
  bun: 'https://bun.sh/docs/installation',
}

for (const [tool, help] of Object.entries(INSTALL_HELP)) {
  if (!Bun.which(tool)) {
    console.error(`${tool} is not installed: ${help}`)
    process.exit(1)
  }
}

if (!existsSync(join(FRONTEND_DIR, 'node_modules'))) {
  console.log('Installing site packages...')
  const install = Bun.spawnSync(['bun', 'install', '--frozen-lockfile'], {
    cwd: FRONTEND_DIR,
    stdout: 'inherit',
    stderr: 'inherit',
  })
  if (install.exitCode !== 0) process.exit(1)
}

const key = ensureDevKey()

const backend = await backendStatus(key)
if (backend === 'other') {
  console.error(
    `Something else runs on ${BACKEND_URL} without our dev key. Stop it and run again.`,
  )
  process.exit(1)
}
if (backend === 'down') {
  console.log(
    'Starting the backend (the first run installs Python packages)...',
  )
  launch('backend', ['uv', 'run', '--locked', 'backend'], BACKEND_DIR, {
    API_KEYS: JSON.stringify({ 'web-dev': key }),
  })
  await waitFor(
    'The backend',
    async () => (await backendStatus(key)) === 'ours',
    180_000,
  )
} else {
  console.log(`Using the backend already running on ${BACKEND_URL}`)
}

if (await reachable(FRONTEND_URL)) {
  console.log(`Using the site already running on ${FRONTEND_URL}`)
} else {
  console.log('Starting the site...')
  launch('site', ['bun', '--hot', 'dev.ts'], FRONTEND_DIR, { API_KEY: key })
  await waitFor(
    'The site',
    async () => (await reachable(FRONTEND_URL))?.ok === true,
    60_000,
  )
}

console.log('Checking the whole path with a dataset video...')
try {
  const result = await smokeTest(FRONTEND_URL)
  console.log(`OK  ${describeResult(result)}`)
} catch (error) {
  console.error(`FAIL  ${error instanceof Error ? error.message : error}`)
  stopAll(1)
}

console.log(`\nReady: ${FRONTEND_URL}  (Ctrl+C stops everything)`)
console.log(`Demo with dataset violations: ${FRONTEND_URL}/?demo`)
if (process.platform === 'darwin') Bun.spawn(['open', FRONTEND_URL])
if (children.length === 0) process.exit(0)

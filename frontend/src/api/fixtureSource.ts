import { sleep as wait } from '@/utils/async'
import { RULES } from '@/rules'
import { lookupLabel } from './labels'
import { JobError, type JobSource } from './source'
import type { JobResponse, JobStatus, Violation } from './types'

export type CaptureFn = (
  file: File,
  times: readonly number[],
) => Promise<{ duration: number; frames: { time: number; base64: string }[] }>

export interface FixtureOptions {
  capture: CaptureFn
  analyzeMs?: number
  uploadMs?: number
  now?: () => number
  sleep?: (ms: number) => Promise<void>
}

interface Entry {
  file: File
  startedAt: number
  result?: Promise<JobResponse>
}

const FRAME_OFFSETS = [-0.6, 0, 0.6]

function noResult(
  jobId: string,
  status: Exclude<JobStatus, 'done'>,
): JobResponse {
  return { job_id: jobId, status, verdict: null, violations: null }
}

export function createFixtureSource({
  capture,
  analyzeMs = 3500,
  uploadMs = 1200,
  now = () => Date.now(),
  sleep = wait,
}: FixtureOptions): JobSource {
  const jobs = new Map<string, Entry>()
  let counter = 0

  async function finish(jobId: string, file: File): Promise<JobResponse> {
    if (/fail/i.test(file.name)) return noResult(jobId, 'failed')

    const label = lookupLabel(file.name)
    if (label.kind !== 'violation') {
      return {
        job_id: jobId,
        status: 'done',
        verdict: 'no_violation',
        violations: [],
      }
    }

    const { frames } = await capture(
      file,
      FRAME_OFFSETS.map((offset) => label.second + offset),
    )
    const evidence = frames.map((frame) => ({
      timestamp_sec: Math.round(frame.time * 10) / 10,
      image_base64: frame.base64,
    }))
    const violations: Violation[] = label.rules.map((id) => ({
      type: RULES.find((rule) => rule.id === id)?.type ?? id,
      timecode_sec: label.second,
      description: label.finding,
      evidence_frames: evidence,
    }))
    return {
      job_id: jobId,
      status: 'done',
      verdict: 'violation',
      violations,
    }
  }

  return {
    async upload(file, onProgress) {
      const steps = 10
      onProgress(0)
      for (let step = 1; step <= steps; step += 1) {
        await sleep(uploadMs / steps)
        onProgress(step / steps)
      }
      counter += 1
      const jobId = `fx-${now().toString(36)}-${counter}`
      jobs.set(jobId, { file, startedAt: now() })
      return { job_id: jobId }
    },

    async getJob(jobId) {
      const entry = jobs.get(jobId)
      if (!entry) throw new JobError('not_found')
      if (now() - entry.startedAt < analyzeMs)
        return noResult(jobId, 'processing')
      entry.result ??= finish(jobId, entry.file).catch(() =>
        noResult(jobId, 'failed'),
      )
      return entry.result
    },
  }
}

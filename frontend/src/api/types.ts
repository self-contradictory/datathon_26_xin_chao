export type JobStatus = 'processing' | 'done' | 'failed'
export type Verdict = 'no_violation' | 'violation'

export interface EvidenceFrame {
  timestamp_sec: number
  image_base64: string
}

export interface RuleSource {
  document: string
  clause: string | null
  url: string | null
  verified?: boolean
  note?: string
  kind?: string
}

export interface Violation {
  type: string
  timecode_sec: number
  description: string
  evidence_frames: EvidenceFrame[]
  rule_id?: string
  source?: RuleSource
}

export interface AnalyzeResponse {
  job_id: string
}

export interface JobResponse {
  job_id: string
  status: JobStatus
  verdict?: Verdict | null
  violations?: Violation[] | null
}

export interface DoneJob {
  job_id: string
  status: 'done'
  verdict: Verdict
  violations: Violation[]
}

export function isDone(job: JobResponse): job is DoneJob {
  return (
    job.status === 'done' &&
    (job.verdict === 'violation' || job.verdict === 'no_violation') &&
    Array.isArray(job.violations)
  )
}

export function showsViolations(job: DoneJob): boolean {
  return job.verdict === 'violation' && job.violations.length > 0
}

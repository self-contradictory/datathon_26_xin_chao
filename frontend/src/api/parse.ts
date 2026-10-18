import { JobError } from './source'
import type {
  AnalyzeResponse,
  EvidenceFrame,
  JobResponse,
  JobStatus,
  RuleSource,
  Verdict,
  Violation,
} from './types'

export class ApiParseError extends JobError {
  readonly path: string

  constructor(path: string, problem: string) {
    super('bad_response', `${path}: ${problem}`)
    this.name = 'ApiParseError'
    this.path = path
  }
}

const STATUSES: readonly JobStatus[] = ['processing', 'done', 'failed']
const VERDICTS: readonly Verdict[] = ['no_violation', 'violation']

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (!isRecord(value)) throw new ApiParseError(path, 'expected an object')
  return value
}

function string(value: unknown, path: string): string {
  if (typeof value !== 'string')
    throw new ApiParseError(path, 'expected a string')
  return value
}

function nonEmptyString(value: unknown, path: string): string {
  if (string(value, path).length === 0) {
    throw new ApiParseError(path, 'expected a non-empty string')
  }
  return value as string
}

function seconds(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new ApiParseError(path, 'expected a number of seconds')
  }
  return value
}

function parseFrame(value: unknown, path: string): EvidenceFrame {
  const frame = record(value, path)
  return {
    timestamp_sec: seconds(frame.timestamp_sec, `${path}.timestamp_sec`),
    image_base64: string(frame.image_base64, `${path}.image_base64`),
  }
}

function parseSource(value: unknown, path: string): RuleSource {
  const source = record(value, path)
  if (source.verified != null && typeof source.verified !== 'boolean') {
    throw new ApiParseError(`${path}.verified`, 'expected a boolean')
  }
  return {
    document: nonEmptyString(source.document, `${path}.document`),
    clause:
      source.clause == null ? null : string(source.clause, `${path}.clause`),
    url: source.url == null ? null : string(source.url, `${path}.url`),
    ...(source.verified == null
      ? {}
      : { verified: source.verified as boolean }),
    ...(source.note == null
      ? {}
      : { note: string(source.note, `${path}.note`) }),
    ...(source.kind == null
      ? {}
      : { kind: string(source.kind, `${path}.kind`) }),
  }
}

function parseViolation(value: unknown, path: string): Violation {
  const violation = record(value, path)
  const frames = violation.evidence_frames
  if (!Array.isArray(frames) || frames.length < 1 || frames.length > 3) {
    throw new ApiParseError(`${path}.evidence_frames`, 'expected 1 to 3 frames')
  }
  return {
    type: string(violation.type, `${path}.type`),
    timecode_sec: seconds(violation.timecode_sec, `${path}.timecode_sec`),
    description: string(violation.description, `${path}.description`),
    evidence_frames: frames.map((frame, i) =>
      parseFrame(frame, `${path}.evidence_frames[${i}]`),
    ),
    ...(violation.rule_id == null
      ? {}
      : { rule_id: nonEmptyString(violation.rule_id, `${path}.rule_id`) }),
    ...(violation.source == null
      ? {}
      : { source: parseSource(violation.source, `${path}.source`) }),
  }
}

export function parseAnalyzeResponse(value: unknown): AnalyzeResponse {
  const body = record(value, 'response')
  return { job_id: nonEmptyString(body.job_id, 'response.job_id') }
}

export function parseJobResponse(value: unknown): JobResponse {
  const body = record(value, 'job')
  const job_id = nonEmptyString(body.job_id, 'job.job_id')

  const status = body.status
  if (!STATUSES.includes(status as JobStatus)) {
    throw new ApiParseError(
      'job.status',
      `expected one of ${STATUSES.join(', ')}`,
    )
  }

  const verdict = body.verdict ?? null
  if (verdict !== null && !VERDICTS.includes(verdict as Verdict)) {
    throw new ApiParseError(
      'job.verdict',
      `expected one of ${VERDICTS.join(', ')}`,
    )
  }

  const rawViolations = body.violations ?? null
  if (rawViolations !== null && !Array.isArray(rawViolations)) {
    throw new ApiParseError('job.violations', 'expected a list')
  }

  if (status === 'done') {
    if (verdict === null)
      throw new ApiParseError('job.verdict', 'required when done')
    if (rawViolations === null) {
      throw new ApiParseError('job.violations', 'required when done')
    }
  }

  return {
    job_id,
    status: status as JobStatus,
    verdict: verdict as Verdict | null,
    violations:
      rawViolations === null
        ? null
        : rawViolations.map((v, i) =>
            parseViolation(v, `job.violations[${i}]`),
          ),
  }
}

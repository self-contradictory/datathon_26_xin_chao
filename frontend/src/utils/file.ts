export type FileProblem =
  { kind: 'not_mov'; extension: string } | { kind: 'empty' }

export interface RejectedFile {
  fileName: string
  problem: FileProblem
}

export function fileExtension(name: string): string {
  const match = /\.([^.\\/]+)$/.exec(name)
  return match ? match[1]!.toLowerCase() : ''
}

export function checkVideoFile(file: {
  name: string
  size: number
}): FileProblem | null {
  const extension = fileExtension(file.name)
  if (extension !== 'mov') return { kind: 'not_mov', extension }
  if (file.size === 0) return { kind: 'empty' }
  return null
}

export type FilePick =
  | { kind: 'single'; file: File }
  | { kind: 'batch'; files: File[]; rejected: RejectedFile[] }
  | { kind: 'none_valid'; count: number }
  | { kind: 'too_many'; count: number; max: number }

export function pickVideos(files: readonly File[], max: number): FilePick {
  const [first] = files
  if (files.length === 1 && first) return { kind: 'single', file: first }
  const accepted: File[] = []
  const rejected: RejectedFile[] = []
  for (const file of files) {
    const problem = checkVideoFile(file)
    if (problem) rejected.push({ fileName: file.name, problem })
    else accepted.push(file)
  }
  if (accepted.length === 0) return { kind: 'none_valid', count: files.length }
  if (accepted.length > max) {
    return { kind: 'too_many', count: accepted.length, max }
  }
  return { kind: 'batch', files: accepted, rejected }
}

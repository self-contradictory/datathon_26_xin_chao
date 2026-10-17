export type FileProblem =
  { kind: 'not_mov'; extension: string } | { kind: 'empty' }

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

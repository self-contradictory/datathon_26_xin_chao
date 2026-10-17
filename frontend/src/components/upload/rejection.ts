import { format, type Messages } from '@/i18n'
import type { FileProblem } from '@/utils/file'

export type RejectionReason =
  | { kind: 'file'; fileName: string; problem: FileProblem }
  | { kind: 'none_valid'; count: number; empty: boolean }
  | { kind: 'too_many'; count: number; max: number }

const VIDEO_EXTENSIONS = new Set([
  '3gp',
  'avi',
  'flv',
  'm2ts',
  'm4v',
  'mkv',
  'mp4',
  'mpeg',
  'mpg',
  'mts',
  'ogv',
  'webm',
  'wmv',
])

function describeFile(
  t: Messages['dropZone'],
  fileName: string,
  problem: FileProblem,
) {
  if (problem.kind === 'empty') {
    return {
      title: t.emptyTitle,
      text: format(t.emptyText, { name: fileName }),
    }
  }
  const ext = problem.extension
  const template = !ext
    ? t.noExtension
    : VIDEO_EXTENSIONS.has(ext)
      ? t.otherVideo
      : t.otherFile
  return {
    title: t.formatTitle,
    text: format(template, { name: fileName, ext }),
  }
}

export function describeRejection(
  t: Messages['dropZone'],
  reason: RejectionReason,
): { title: string; text: string } {
  switch (reason.kind) {
    case 'file':
      return describeFile(t, reason.fileName, reason.problem)
    case 'none_valid':
      return {
        title: t.noneValidTitle,
        text: format(reason.empty ? t.noneValidEmptyText : t.noneValidText, {
          count: reason.count,
        }),
      }
    case 'too_many':
      return {
        title: t.tooManyTitle,
        text: format(t.tooManyText, { count: reason.count, max: reason.max }),
      }
  }
}

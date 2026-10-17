import { BatchScreen } from '@/screens/Batch'
import type { BatchRowView } from '@/screens/contracts'
import { ReportScreen } from '@/screens/Report'
import { openedReport } from './batch'
import type { BatchItem } from './types'
import type { useBatchFlow } from './useBatchFlow'

function toRow({ id, video, stage }: BatchItem): BatchRowView {
  return {
    id,
    fileName: video.file.name,
    fileSize: video.file.size,
    duration: video.duration,
    posterUrl: video.posterUrl,
    stage,
  }
}

export function BatchFlow({
  batch,
  onStartOver,
}: {
  batch: ReturnType<typeof useBatchFlow>
  onStartOver: () => void
}) {
  const { state, open, close, retry } = batch
  const opened = openedReport(state)

  if (opened) {
    const { item, result } = opened
    return (
      <ReportScreen
        key={item.id}
        job={result.job}
        fileName={item.video.file.name}
        fileSize={item.video.file.size}
        duration={item.video.duration}
        videoUrl={item.video.url}
        posterUrl={item.video.posterUrl}
        checkedAt={result.checkedAt}
        file={item.video.file}
        exit={{ kind: 'backToList', onClick: close }}
      />
    )
  }

  return (
    <BatchScreen
      rows={state.items.map(toRow)}
      rejected={state.rejected}
      pausedBy={state.pausedBy}
      returnFocusId={state.lastOpenedId}
      onOpen={open}
      onRetry={retry}
      onStartOver={onStartOver}
    />
  )
}

import { batchCounts } from '@/batch/batch'
import { lazy, Suspense, useEffect, useState } from 'react'
import { showsViolations, type DoneJob } from '@/api/types'
import { openedReport } from '@/batch/batch'
import { BatchFlow } from '@/batch/BatchFlow'
import type { BatchState } from '@/batch/types'
import { useBatchFlow } from '@/batch/useBatchFlow'
import { Header } from '@/components/Header'
import { jobSource, POLL_INTERVAL_MS, POLL_TIMEOUT_MS } from '@/config'
import { useJobFlow, type FlowState } from '@/flow'
import { format, useStrings, type Messages } from '@/i18n'
import { LangProvider } from '@/i18n/LangProvider'
import { useHashRoute } from '@/route'
import { ApiDocsPage } from '@/screens/ApiDocs'
import { ProcessingScreen } from '@/screens/Processing'
import { ReportScreen } from '@/screens/Report'
import { HistoryPage } from '@/screens/History'
import { HistoryReport } from '@/screens/HistoryReport'
import { RulesPage } from '@/screens/Rules'
import { UploadScreen } from '@/screens/Upload'
import { useStrayDropGuard } from '@/useStrayDropGuard'

const DemoPage =
  process.env.NODE_ENV === 'production'
    ? null
    : lazy(() => import('@/demo/DemoPage'))

function MainFlow({
  flow,
  batch,
}: {
  flow: ReturnType<typeof useJobFlow>
  batch: ReturnType<typeof useBatchFlow>
}) {
  const { state, start, retry, reset } = flow
  const [restarted, setRestarted] = useState(false)
  const startOver = (stop: () => void) => () => {
    setRestarted(true)
    stop()
  }

  if (batch.state.items.length > 0) {
    return <BatchFlow batch={batch} onStartOver={startOver(batch.reset)} />
  }

  if (state.screen === 'upload') {
    return (
      <UploadScreen
        onSubmit={start}
        onSubmitMany={(files, rejected) => {
          reset()
          batch.start(files, rejected)
        }}
        focusTitle={restarted}
      />
    )
  }

  if (state.screen === 'processing') {
    return (
      <ProcessingScreen
        fileName={state.video.file.name}
        fileSize={state.video.file.size}
        duration={state.video.duration}
        posterUrl={state.video.posterUrl}
        phase={state.phase}
        uploadProgress={state.uploadProgress}
        startedAt={state.startedAt}
        stoppedAt={state.stoppedAt}
        error={state.error}
        failedStep={state.failedStep}
        onRetry={retry}
        onNewVideo={startOver(reset)}
      />
    )
  }

  return (
    <ReportScreen
      job={state.job}
      fileName={state.video.file.name}
      fileSize={state.video.file.size}
      duration={state.video.duration}
      videoUrl={state.video.url}
      posterUrl={state.video.posterUrl}
      checkedAt={state.checkedAt}
      file={state.video.file}
      exit={{ kind: 'newVideo', onClick: startOver(reset) }}
    />
  )
}

function verdictTitle(job: DoneJob): keyof Messages['titles'] {
  return showsViolations(job) ? 'violation' : 'clean'
}

function mainTitleKey(
  flow: FlowState,
  batch: BatchState,
): keyof Messages['titles'] {
  if (batch.items.length > 0) {
    const opened = openedReport(batch)
    return opened ? verdictTitle(opened.result.job) : 'batch'
  }
  if (flow.screen !== 'report') return flow.screen
  return verdictTitle(flow.job)
}

function Shell() {
  useStrayDropGuard()
  const route = useHashRoute()
  const polling = { intervalMs: POLL_INTERVAL_MS, timeoutMs: POLL_TIMEOUT_MS }
  const flow = useJobFlow(jobSource, polling)
  const batch = useBatchFlow(jobSource, polling)
  const goHome = () => {
    const busy =
      flow.state.screen === 'processing' ||
      batchCounts(batch.state.items).unfinished > 0
    if (busy) return
    flow.reset()
    batch.reset()
  }
  const t = useStrings('titles')
  const page = route.page === 'demo' && !DemoPage ? 'main' : route.page

  const headerRoute =
    page === 'rules' || page === 'api' || page === 'history'
      ? page
      : page === 'check'
        ? 'history'
        : 'main'
  const titleKey =
    headerRoute === 'main' ? mainTitleKey(flow.state, batch.state) : headerRoute
  const recheck = (file: File) => {
    batch.reset()
    window.location.hash = '#/'
    void flow.start(file, true)
  }
  const documentTitle = format(t.suffix, { title: t[titleKey] })
  useEffect(() => {
    document.title = documentTitle
  }, [documentTitle])

  return (
    <div className="min-h-svh bg-canvas font-sans text-body text-text">
      <Header route={headerRoute} onHome={goHome} />
      {route.page === 'rules' && <RulesPage focusRuleId={route.ruleId} />}
      {page === 'api' && <ApiDocsPage />}
      {page === 'history' && <HistoryPage />}
      {route.page === 'check' && (
        <HistoryReport jobId={route.jobId} onRecheck={recheck} />
      )}
      {route.page === 'demo' && DemoPage && (
        <Suspense fallback={null}>
          <DemoPage state={route.state} />
        </Suspense>
      )}
      <div hidden={page !== 'main'}>
        <MainFlow flow={flow} batch={batch} />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <LangProvider>
      <Shell />
    </LangProvider>
  )
}

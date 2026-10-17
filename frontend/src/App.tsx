import { lazy, Suspense, useEffect } from 'react'
import { showsViolations } from '@/api/types'
import { Header } from '@/components/Header'
import { jobSource, POLL_INTERVAL_MS, POLL_TIMEOUT_MS } from '@/config'
import { useJobFlow, type FlowState } from '@/flow'
import { format, useStrings, type Messages } from '@/i18n'
import { LangProvider } from '@/i18n/LangProvider'
import { useHashRoute } from '@/route'
import { ApiDocsPage } from '@/screens/ApiDocs'
import { ProcessingScreen } from '@/screens/Processing'
import { ReportScreen } from '@/screens/Report'
import { RulesPage } from '@/screens/Rules'
import { UploadScreen } from '@/screens/Upload'
import { useStrayDropGuard } from '@/useStrayDropGuard'

const DemoPage =
  process.env.NODE_ENV === 'production'
    ? null
    : lazy(() => import('@/demo/DemoPage'))

function MainFlow({ flow }: { flow: ReturnType<typeof useJobFlow> }) {
  const { state, start, retry, reset } = flow

  if (state.screen === 'upload') return <UploadScreen onSubmit={start} />

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
        onNewVideo={reset}
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
      onNewVideo={reset}
    />
  )
}

function mainTitleKey(state: FlowState): keyof Messages['titles'] {
  if (state.screen !== 'report') return state.screen
  return showsViolations(state.job) ? 'violation' : 'clean'
}

function Shell() {
  useStrayDropGuard()
  const route = useHashRoute()
  const flow = useJobFlow(jobSource, {
    intervalMs: POLL_INTERVAL_MS,
    timeoutMs: POLL_TIMEOUT_MS,
  })
  const t = useStrings('titles')
  const page = route.page === 'demo' && !DemoPage ? 'main' : route.page

  const titleKey =
    page === 'rules' || page === 'api' ? page : mainTitleKey(flow.state)
  const documentTitle = format(t.suffix, { title: t[titleKey] })
  useEffect(() => {
    document.title = documentTitle
  }, [documentTitle])

  return (
    <div className="min-h-svh bg-bg font-sans text-body text-text">
      <Header route={page === 'rules' || page === 'api' ? page : 'main'} />
      {page === 'rules' && <RulesPage />}
      {page === 'api' && <ApiDocsPage />}
      {route.page === 'demo' && DemoPage && (
        <Suspense fallback={null}>
          <DemoPage state={route.state} />
        </Suspense>
      )}
      <div hidden={page !== 'main'}>
        <MainFlow flow={flow} />
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

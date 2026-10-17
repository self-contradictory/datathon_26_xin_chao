import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ActDocument } from '@/components/act/ActDocument'
import { buildReportModel } from '@/components/act/model'
import { usePrintAct } from '@/components/act/usePrintAct'
import { IconButton } from '@/components/report/IconButton'
import { fullJson } from '@/components/report/json'
import { saveFile } from '@/utils/download'
import { showsViolations } from '@/api/types'
import { Button } from '@/components/Button'
import { ChevronLeftIcon, DownloadIcon, PlusIcon } from '@/components/icons'
import {
  Player,
  type PlayerHandle,
  type PlayerMarker,
} from '@/components/report/player/Player'
import { panelId, tabId } from '@/components/tabIds'
import { Tabs } from '@/components/Tabs'
import { format, useStrings } from '@/i18n'
import { formatTime } from '@/utils/time'
import { JsonView } from '@/components/report/JsonView'
import {
  activeViolationIndex,
  stepIndex,
} from '@/components/report/activeViolation'
import { ReportMeta } from '@/components/report/ReportMeta'
import { isTypingTarget } from '@/utils/keys'
import { nextUnreviewed, reviewSummary } from '@/history/review'
import type { ReviewDecision } from '@/history/types'
import { useCheckRecord } from '@/history/useCheckRecord'
import { useViolationText } from '@/components/report/violationText'
import { VerdictSummary } from '@/components/report/VerdictSummary'
import { ViolationList } from '@/components/report/ViolationList'
import type { ReportScreenProps } from './contracts'

type Tab = 'report' | 'json'
const TABS = 'report'

export function ReportScreen({
  job,
  fileName,
  fileSize,
  duration,
  videoUrl,
  posterUrl,
  checkedAt,
  file,
  exit,
}: ReportScreenProps) {
  const t = useStrings('report')
  const [tab, setTab] = useState<Tab>('report')
  const [selected, setSelected] = useState<number | null>(0)
  const [picked, setPicked] = useState(false)
  const playerRef = useRef<PlayerHandle>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => titleRef.current?.focus(), [])

  useEffect(() => {
    const pause = () => playerRef.current?.pause()
    window.addEventListener('hashchange', pause)
    return () => window.removeEventListener('hashchange', pause)
  }, [])

  const { violations } = job
  const count = violations.length
  const hasViolations = showsViolations(job)
  const activeIndex = selected !== null && selected < count ? selected : null
  const active =
    hasViolations && activeIndex !== null ? violations[activeIndex] : undefined
  const { record, review, decide } = useCheckRecord({
    job,
    fileName,
    fileSize,
    checkedAt,
    file,
  })
  const summary = reviewSummary(review, hasViolations ? count : 0)

  const { typeName } = useViolationText()
  const markers: PlayerMarker[] = hasViolations
    ? violations.map((violation, index) => ({
        id: String(index),
        position: index + 1,
        time: violation.timecode_sec,
        label: typeName(violation.type),
        dimmed: review[index]?.decision === 'rejected',
      }))
    : []
  const [playhead, setPlayhead] = useState<number | null>(null)
  const rows = useRef(new Map<number, HTMLLIElement>())

  useEffect(() => {
    const first = violations[0]
    if (hasViolations && first) playerRef.current?.seek(first.timecode_sec)
  }, [hasViolations, violations])

  function select(index: number, reveal = false) {
    const violation = violations[index]
    if (!violation) return
    setSelected(index)
    setPicked(true)
    playerRef.current?.seek(violation.timecode_sec)
    if (reveal) requestAnimationFrame(() => revealRow(index))
  }

  async function mark(index: number, decision: ReviewDecision | null) {
    await decide(index, decision)
    if (!decision) return
    const next = nextUnreviewed(
      { ...review, [index]: { decision, at: 0 } },
      count,
      index,
    )
    if (next === null) setSelected(null)
    else select(next, true)
  }

  function revealRow(index: number) {
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    rows.current
      .get(index)
      ?.scrollIntoView({ behavior: calm ? 'auto' : 'smooth', block: 'nearest' })
  }

  const onStepKey = useEffectEvent((event: KeyboardEvent) => {
    if (!hasViolations || tab !== 'report') return
    if (event.altKey || event.ctrlKey || event.metaKey) return
    if (isTypingTarget(event.target)) return
    if (
      activeIndex !== null &&
      (event.code === 'KeyY' || event.code === 'KeyX')
    ) {
      event.preventDefault()
      void mark(activeIndex, event.code === 'KeyY' ? 'confirmed' : 'rejected')
      return
    }
    const by = event.code === 'KeyN' ? 1 : event.code === 'KeyP' ? -1 : 0
    if (!by) return
    event.preventDefault()
    select(stepIndex(activeIndex ?? (by === 1 ? -1 : 0), by, count), true)
  })

  useEffect(() => {
    const listener = (event: KeyboardEvent) => onStepKey(event)
    document.addEventListener('keydown', listener)
    return () => document.removeEventListener('keydown', listener)
  }, [])

  const verdictTitle = useStrings('verdictSummary')
  const act = useStrings('act')
  const printer = usePrintAct()

  function download() {
    const reviewed = hasViolations ? review : {}
    const base = fileName.replace(/\.[^.]+$/, '')
    if (tab === 'json') {
      saveFile(`${base}.json`, fullJson(job, reviewed), 'application/json')
      return
    }
    if (!record) return
    const model = buildReportModel({ ...record, review: reviewed }, duration)
    const date = new Date(checkedAt).toISOString().slice(0, 10)
    printer.print(model, format(act.documentName, { file: base, date }))
  }

  return (
    <main className="mx-auto w-full max-w-[1200px] px-4 pt-6 pb-16 sm:px-6 lg:pt-8">
      <h1 ref={titleRef} tabIndex={-1} className="sr-only">
        {hasViolations
          ? format(verdictTitle.violation, { n: count })
          : verdictTitle.clean}
      </h1>

      <div className="grid gap-6 lg:grid-cols-[var(--player-width)_minmax(0,1fr)] lg:grid-rows-[auto_auto_1fr] lg:items-start lg:gap-x-8">
        <div className="flex flex-wrap items-center justify-between gap-3 lg:col-start-2 lg:row-start-1">
          <ReportMeta
            fileName={fileName}
            fileSize={fileSize}
            duration={duration}
            checkedAt={checkedAt}
          />
          <div className="flex items-center gap-2">
            <Tabs
              items={[
                { key: 'report', label: t.report },
                { key: 'json', label: t.json },
              ]}
              value={tab}
              onChange={setTab}
              idPrefix={TABS}
              label={t.tabs}
            />
            <IconButton
              label={tab === 'report' ? act.downloadAct : act.downloadJson}
              onClick={download}
            >
              <DownloadIcon size={20} />
            </IconButton>
          </div>
        </div>

        <VerdictSummary
          violation={hasViolations}
          count={count}
          review={summary}
          className="lg:col-start-2 lg:row-start-2"
        />

        <div className="mx-auto flex w-full max-w-[400px] flex-col gap-3 lg:col-start-1 lg:row-span-3 lg:row-start-1 lg:mx-0">
          {exit.kind === 'backToList' && (
            <Button
              variant="secondary"
              icon={<ChevronLeftIcon size={20} />}
              onClick={exit.onClick}
              className="self-start"
            >
              {t.backToList}
            </Button>
          )}
          <Player
            ref={playerRef}
            src={videoUrl}
            posterUrl={posterUrl}
            duration={duration}
            markers={markers}
            activeMarkerId={playhead === null ? null : String(playhead)}
            onMarkerSelect={(id) => select(Number(id), true)}
            onTimeChange={(time) =>
              setPlayhead(activeViolationIndex(violations, time))
            }
          />
          {exit.kind === 'newVideo' && (
            <Button
              icon={<PlusIcon size={20} />}
              onClick={exit.onClick}
              className="mt-1 w-full"
            >
              {t.newVideo}
            </Button>
          )}
        </div>

        <div className="min-w-0 lg:col-start-2 lg:row-start-3">
          <div
            role="tabpanel"
            id={panelId(TABS, 'report')}
            aria-labelledby={tabId(TABS, 'report')}
            hidden={tab !== 'report'}
          >
            {hasViolations && (
              <ViolationList
                violations={violations}
                openIndex={activeIndex}
                playheadIndex={playhead}
                review={review}
                onSelect={select}
                onDecide={(index, decision) => void mark(index, decision)}
                rowRef={(index, row) => {
                  if (row) rows.current.set(index, row)
                  else rows.current.delete(index)
                }}
              />
            )}
          </div>

          <div
            role="tabpanel"
            id={panelId(TABS, 'json')}
            aria-labelledby={tabId(TABS, 'json')}
            hidden={tab !== 'json'}
          >
            <JsonView job={job} review={hasViolations ? review : {}} />
          </div>
        </div>
      </div>

      {printer.printing &&
        printer.root &&
        createPortal(
          <ActDocument model={printer.printing.model} />,
          printer.root,
        )}

      <p aria-live="polite" className="sr-only">
        {picked && active && activeIndex !== null
          ? format(t.selected, {
              i: activeIndex + 1,
              n: count,
              type: typeName(active.type),
              time: formatTime(active.timecode_sec),
            })
          : ''}
      </p>
    </main>
  )
}

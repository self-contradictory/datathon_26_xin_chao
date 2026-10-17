import { useEffect, useMemo, useRef, useState } from 'react'
import { showsViolations } from '@/api/types'
import { Button } from '@/components/Button'
import { ChevronLeftIcon, PlusIcon } from '@/components/icons'
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
import { ReportMeta } from '@/components/report/ReportMeta'
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
  exit,
}: ReportScreenProps) {
  const t = useStrings('report')
  const [tab, setTab] = useState<Tab>('report')
  const [selected, setSelected] = useState(0)
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
  const activeIndex = selected < count ? selected : 0
  const active = hasViolations ? violations[activeIndex] : undefined

  const markers = useMemo<PlayerMarker[]>(
    () =>
      hasViolations
        ? violations.map((violation, index) => ({
            id: String(index),
            time: violation.timecode_sec,
            label: violation.type,
          }))
        : [],
    [hasViolations, violations],
  )

  useEffect(() => {
    const first = violations[0]
    if (hasViolations && first) playerRef.current?.seek(first.timecode_sec)
  }, [hasViolations, violations])

  function select(index: number) {
    const violation = violations[index]
    if (!violation) return
    setSelected(index)
    setPicked(true)
    playerRef.current?.seek(violation.timecode_sec)
  }

  const verdictTitle = useStrings('verdictSummary')

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
        </div>

        <VerdictSummary
          violation={hasViolations}
          count={count}
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
            activeMarkerId={active ? String(activeIndex) : null}
            onMarkerSelect={(id) => select(Number(id))}
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
            {active && (
              <ViolationList
                violations={violations}
                activeIndex={activeIndex}
                onSelect={select}
              />
            )}
          </div>

          <div
            role="tabpanel"
            id={panelId(TABS, 'json')}
            aria-labelledby={tabId(TABS, 'json')}
            hidden={tab !== 'json'}
          >
            <JsonView job={job} />
          </div>
        </div>
      </div>

      <p aria-live="polite" className="sr-only">
        {picked && active
          ? format(t.selected, {
              i: activeIndex + 1,
              n: count,
              type: active.type,
              time: formatTime(active.timecode_sec),
            })
          : ''}
      </p>
    </main>
  )
}

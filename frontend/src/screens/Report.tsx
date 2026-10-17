import { useEffect, useMemo, useRef, useState } from 'react'
import { showsViolations } from '@/api/types'
import { Button } from '@/components/Button'
import { PlusIcon } from '@/components/icons'
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
import { TimeChip } from '@/components/report/TimeChip'
import { VerdictSummary } from '@/components/report/VerdictSummary'
import { ViolationCard } from '@/components/report/ViolationCard'
import { CleanSummary, ViolationList } from '@/components/report/ViolationList'
import type { ReportScreenProps } from './contracts'
import { wrapIndex } from '@/utils/wrap'

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
  onNewVideo,
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

  function changeTab(next: Tab) {
    if (next !== 'report') playerRef.current?.pause()
    setTab(next)
  }

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

  return (
    <main>
      <div className="border-b border-border">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-4 gap-y-2 px-4 pt-2 sm:px-6">
          <Tabs
            items={[
              { key: 'report', label: t.report },
              { key: 'json', label: t.json },
            ]}
            value={tab}
            onChange={changeTab}
            idPrefix={TABS}
            label={t.tabs}
          />
          <Button
            variant="secondary"
            icon={<PlusIcon size={20} />}
            onClick={onNewVideo}
            className="my-0.5 ml-auto"
          >
            {t.newVideo}
          </Button>
        </div>
      </div>

      <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 pt-6 pb-16 sm:px-6">
        <div
          role="tabpanel"
          id={panelId(TABS, 'report')}
          aria-labelledby={tabId(TABS, 'report')}
          hidden={tab !== 'report'}
        >
          <div className="grid gap-6 lg:grid-cols-[var(--player-width)_minmax(0,1fr)] lg:grid-rows-[auto_1fr] lg:items-start">
            <VerdictSummary
              titleRef={titleRef}
              violation={hasViolations}
              count={count}
              fileName={fileName}
              fileSize={fileSize}
              duration={duration}
              checkedAt={checkedAt}
              className="lg:col-start-2"
            >
              {!active && <CleanSummary />}
            </VerdictSummary>

            <div className="mx-auto flex w-full max-w-[400px] flex-col gap-3 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:mx-0">
              <Player
                ref={playerRef}
                src={videoUrl}
                posterUrl={posterUrl}
                duration={duration}
                markers={markers}
                activeMarkerId={active ? String(activeIndex) : null}
                onMarkerSelect={(id) => select(Number(id))}
              />
              {active && (
                <p className="hidden flex-wrap items-center gap-2 lg:flex">
                  <span
                    aria-hidden="true"
                    className="h-3 w-1 rounded-[1px] bg-danger"
                  />
                  <TimeChip seconds={active.timecode_sec} />
                  <span lang="ru" className="font-semibold">
                    {active.type}
                  </span>
                </p>
              )}
            </div>

            {active && (
              <div className="flex min-w-0 flex-col gap-6 lg:col-start-2">
                <ViolationList
                  violations={violations}
                  activeIndex={activeIndex}
                  onSelect={select}
                />
                <ViolationCard
                  violation={active}
                  index={activeIndex}
                  total={count}
                  onStep={(by) => select(wrapIndex(activeIndex, by, count))}
                />
              </div>
            )}
          </div>
        </div>

        <div
          role="tabpanel"
          id={panelId(TABS, 'json')}
          aria-labelledby={tabId(TABS, 'json')}
          hidden={tab !== 'json'}
        >
          <JsonView job={job} />
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
      </div>
    </main>
  )
}

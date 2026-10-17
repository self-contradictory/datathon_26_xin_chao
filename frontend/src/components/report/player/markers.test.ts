import { describe, expect, test } from 'bun:test'
import { fallbackSpan, groupMarkers, tooltipAlign } from './markers'

const marker = (id: string, time: number) => ({
  id,
  position: 1,
  time,
  label: id,
})

describe('groupMarkers', () => {
  test('sorts by time and keeps distant markers apart', () => {
    const groups = groupMarkers([marker('b', 10), marker('a', 2)], 20, 400)
    expect(groups.map((g) => g.first.id)).toEqual(['a', 'b'])
    expect(groups.map((g) => g.ratio)).toEqual([0.1, 0.5])
  })

  test('merges markers closer than 24 px', () => {
    const groups = groupMarkers(
      [marker('a', 10), marker('b', 15), marker('c', 30)],
      100,
      400,
    )
    expect(groups.map((g) => g.items.map((m) => m.id))).toEqual([
      ['a', 'b'],
      ['c'],
    ])
  })

  test('clamps markers past the end and handles an unknown span', () => {
    expect(groupMarkers([marker('a', 50)], 20, 400)[0]?.ratio).toBe(1)
    expect(groupMarkers([marker('a', 5)], 0, 400)).toEqual([])
  })
})

test('fallbackSpan puts the latest marker at 80%', () => {
  expect(fallbackSpan([marker('a', 8), marker('b', 4)])).toBe(10)
  expect(fallbackSpan([])).toBe(0)
})

test('tooltipAlign keeps a 240 px tooltip inside the track', () => {
  expect(tooltipAlign(0.26, 320)).toBe('start')
  expect(tooltipAlign(0.5, 400)).toBe('center')
  expect(tooltipAlign(0.9, 400)).toBe('end')
})

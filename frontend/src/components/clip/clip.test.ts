import { describe, expect, test } from 'bun:test'
import { clipFileName, clipWindow, pickRecorderMime } from './clip'

describe('clipWindow', () => {
  test('two seconds before and three after', () => {
    expect(clipWindow(10, 30)).toEqual({ start: 8, end: 13 })
  })

  test('an event at the first second starts at zero', () => {
    expect(clipWindow(1, 30)).toEqual({ start: 0, end: 4 })
  })

  test('an event in the last two seconds stops at the end', () => {
    expect(clipWindow(29, 30)).toEqual({ start: 27, end: 30 })
  })

  test('an unknown duration keeps the full window', () => {
    expect(clipWindow(5, null)).toEqual({ start: 3, end: 8 })
  })
})

describe('pickRecorderMime', () => {
  test('prefers mp4 with avc1', () => {
    expect(pickRecorderMime(() => true)).toEqual({
      mime: 'video/mp4;codecs=avc1',
      ext: 'mp4',
    })
  })

  test('falls back to webm', () => {
    expect(pickRecorderMime((mime) => mime === 'video/webm')).toEqual({
      mime: 'video/webm',
      ext: 'webm',
    })
  })

  test('nothing supported means no clip', () => {
    expect(pickRecorderMime(() => false)).toBeNull()
  })
})

describe('clipFileName', () => {
  test('uses the file name and the time without the extension', () => {
    expect(clipFileName('Х-17.mov', '0:07', 'mp4')).toBe('Х-17_0-07.mp4')
  })
})

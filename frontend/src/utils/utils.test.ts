import { describe, expect, test } from 'bun:test'
import { messagesFor } from '@/i18n'
import { LABEL_COUNT, labelKey, lookupLabel } from '@/api/labels'
import { parseHash } from '@/route'
import { findRule, RULES } from '@/rules'
import { checkVideoFile, fileExtension } from './file'
import { clampTime } from './frames'
import { formatFileSize, formatFrameTime, formatTime } from './time'

describe('time', () => {
  test('formatTime', () => {
    expect(formatTime(0)).toBe('00:00')
    expect(formatTime(7)).toBe('00:07')
    expect(formatTime(7.9)).toBe('00:07')
    expect(formatTime(68)).toBe('01:08')
    expect(formatTime(142.5)).toBe('02:22')
    expect(formatTime(3725)).toBe('1:02:05')
    expect(formatTime(-3)).toBe('00:00')
    expect(formatTime(Number.NaN)).toBe('00:00')
  })

  test('formatFrameTime keeps tenths', () => {
    expect(formatFrameTime(6.8)).toBe('00:06.8')
    expect(formatFrameTime(7)).toBe('00:07.0')
    expect(formatFrameTime(44.25)).toBe('00:44.3')
    expect(formatFrameTime(59.96)).toBe('01:00.0')
  })

  test('formatFileSize uses a decimal comma', () => {
    const ru = messagesFor('units', 'ru')
    expect(formatFileSize(3032008, 'ru-RU', ru)).toBe('2,9 МБ')
    expect(formatFileSize(28718927, 'ru-RU', ru)).toBe('27,4 МБ')
    expect(formatFileSize(512, 'ru-RU', ru)).toBe('512 Б')
    expect(formatFileSize(3032008, 'en-GB', messagesFor('units', 'en'))).toBe(
      '2.9 MB',
    )
  })
})

describe('file check', () => {
  test('only .mov, any case, no size limit', () => {
    expect(checkVideoFile({ name: 'Х-17.mov', size: 1 })).toBeNull()
    expect(checkVideoFile({ name: 'CLIP.MOV', size: 1 })).toBeNull()
    expect(checkVideoFile({ name: 'big.mov', size: 5 * 1024 ** 3 })).toBeNull()
    expect(checkVideoFile({ name: 'Х-17.mp4', size: 1 })).toEqual({
      kind: 'not_mov',
      extension: 'mp4',
    })
    expect(checkVideoFile({ name: 'noext', size: 1 })).toEqual({
      kind: 'not_mov',
      extension: '',
    })
    expect(checkVideoFile({ name: 'a.mov', size: 0 })).toEqual({
      kind: 'empty',
    })
  })

  test('fileExtension', () => {
    expect(fileExtension('a.b.MOV')).toBe('mov')
    expect(fileExtension('.mov')).toBe('mov')
    expect(fileExtension('dir.mov/file')).toBe('')
  })
})

describe('dataset labels', () => {
  test('42 labelled videos', () => {
    expect(LABEL_COUNT).toBe(42)
  })

  test('Cyrillic Х and Latin X map to the same key', () => {
    expect(labelKey('Х-17.mov')).toBe('X-17')
    expect(labelKey('X-1.mov')).toBe('X-1')
    expect(labelKey('х-04.MOV')).toBe('X-4')
  })

  test('lookup', () => {
    expect(lookupLabel('Х-17.mov')).toEqual({ kind: 'violation', second: 7 })
    expect(lookupLabel('X-1.mov')).toEqual({ kind: 'violation', second: 22 })
    expect(lookupLabel('Х-47.mov')).toEqual({ kind: 'violation', second: 68 })
    expect(lookupLabel('Х-3.mov')).toEqual({ kind: 'clean' })
    expect(lookupLabel('my-video.mov')).toEqual({ kind: 'unknown' })
  })
})

describe('frames', () => {
  test('clampTime keeps seeks inside the video', () => {
    expect(clampTime(-0.6, 14.7)).toBe(0)
    expect(clampTime(7, 14.7)).toBe(7)
    expect(clampTime(20, 14.7)).toBeCloseTo(14.65)
    expect(clampTime(1, 0)).toBe(0)
  })
})

describe('rules', () => {
  test('findRule ignores case, ё and extra spaces', () => {
    expect(findRule('наличные  вне зоны видимости камеры ')).toBe(RULES[0]!)
    expect(findRule('Пересчет не на виду у клиента')).toBe(RULES[3]!)
    expect(findRule('Неизвестный тип')).toBeNull()
  })
})

describe('route', () => {
  test('parseHash', () => {
    expect(parseHash('')).toEqual({ page: 'main' })
    expect(parseHash('#/')).toEqual({ page: 'main' })
    expect(parseHash('#/rules')).toEqual({ page: 'rules' })
    expect(parseHash('#/api/')).toEqual({ page: 'api' })
    expect(parseHash('#/demo/report-one')).toEqual({
      page: 'demo',
      state: 'report-one',
    })
    expect(parseHash('#/unknown')).toEqual({ page: 'main' })
  })
})

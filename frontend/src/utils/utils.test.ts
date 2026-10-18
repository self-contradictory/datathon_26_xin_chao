import { describe, expect, test } from 'bun:test'
import { messagesFor } from '@/i18n'
import { LABEL_COUNT, labelKey, lookupLabel } from '@/api/labels'
import { parseHash } from '@/route'
import { findRule } from '@/rules'
import { checkVideoFile, fileExtension, pickVideos } from './file'
import { clampTime } from './frames'
import {
  formatFileSize,
  formatFrameTime,
  formatFullDate,
  formatShortDate,
  formatTime,
} from './time'

describe('time', () => {
  test('formatShortDate', () => {
    expect(formatShortDate(new Date(2026, 9, 17, 18, 5).getTime())).toBe(
      '17.10 · 18:05',
    )
    expect(formatFullDate(new Date(2026, 9, 17, 18, 5).getTime())).toBe(
      '17.10.2026 · 18:05',
    )
  })

  test('formatTime', () => {
    expect(formatTime(0)).toBe('0:00')
    expect(formatTime(7)).toBe('0:07')
    expect(formatTime(7.9)).toBe('0:07')
    expect(formatTime(68)).toBe('1:08')
    expect(formatTime(142.5)).toBe('2:22')
    expect(formatTime(3725)).toBe('1:02:05')
    expect(formatTime(-3)).toBe('0:00')
    expect(formatTime(Number.NaN)).toBe('0:00')
  })

  test('formatFrameTime keeps tenths', () => {
    expect(formatFrameTime(6.8)).toBe('0:06.8')
    expect(formatFrameTime(7)).toBe('0:07.0')
    expect(formatFrameTime(44.25)).toBe('0:44.3')
    expect(formatFrameTime(59.96)).toBe('1:00.0')
  })

  test('formatFileSize uses a decimal comma', () => {
    const ru = messagesFor('units', 'ru')
    expect(formatFileSize(3032008, 'ru-RU', ru)).toBe('2,9 МБ')
    expect(formatFileSize(28718927, 'ru-RU', ru)).toBe('27,4 МБ')
    expect(formatFileSize(512, 'ru-RU', ru)).toBe('512 Б')
    expect(formatFileSize(1024 * 1024 - 100, 'ru-RU', ru)).toBe('1,0 МБ')
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

describe('pickVideos', () => {
  const video = (name: string, size = 1) =>
    new File([new Uint8Array(size)], name)

  test('one file keeps the single-video path, even a wrong one', () => {
    const one = video('Х-3.mov')
    expect(pickVideos([one], 10)).toEqual({ kind: 'single', file: one })
    const wrong = video('Х-3.mp4')
    expect(pickVideos([wrong], 10)).toEqual({ kind: 'single', file: wrong })
  })

  test('several files become a batch in the chosen order', () => {
    const files = [video('b.mov'), video('a.mov')]
    expect(pickVideos(files, 10)).toEqual({
      kind: 'batch',
      files,
      rejected: [],
    })
  })

  test('wrong files are listed and the rest are still checked', () => {
    const good = video('a.mov')
    expect(pickVideos([video('b.mp4'), good, video('c.mov', 0)], 10)).toEqual({
      kind: 'batch',
      files: [good],
      rejected: [
        { fileName: 'b.mp4', problem: { kind: 'not_mov', extension: 'mp4' } },
        { fileName: 'c.mov', problem: { kind: 'empty' } },
      ],
    })
  })

  test('no usable file at all is an error', () => {
    expect(pickVideos([video('a.mp4'), video('b.txt')], 10)).toEqual({
      kind: 'none_valid',
      count: 2,
      empty: false,
    })
    expect(pickVideos([video('a.mov', 0), video('b.mov', 0)], 10)).toEqual({
      kind: 'none_valid',
      count: 2,
      empty: true,
    })
  })

  test('the limit counts only usable files', () => {
    const ten = Array.from({ length: 10 }, (_, i) => video(`${i}.mov`))
    expect(pickVideos(ten, 10).kind).toBe('batch')
    expect(pickVideos([...ten, video('x.mp4')], 10).kind).toBe('batch')
    expect(pickVideos([...ten, video('10.mov')], 10)).toEqual({
      kind: 'too_many',
      count: 11,
      max: 10,
    })
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
    expect(lookupLabel('Х-17.mov')).toMatchObject({
      kind: 'violation',
      second: 7,
      rules: ['noId'],
    })
    expect(lookupLabel('X-1.mov')).toMatchObject({
      kind: 'violation',
      second: 22,
    })
    expect(lookupLabel('Х-47.mov')).toMatchObject({
      kind: 'violation',
      second: 68,
      rules: ['cashLeftOut', 'mixedCash'],
    })
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
    expect(findRule('клиент  обслужен без удостоверения личности ')?.id).toBe(
      'noId',
    )
    expect(findRule('Пересчет без клиента')?.id).toBe('countWithoutClient')
    expect(
      findRule('Кассир покинул рабочее место до окончания обслуживания клиента')
        ?.id,
    ).toBe('leftDuringService')
    expect(findRule('Мобильный телефон в кассовом узле')?.id).toBe(
      'mobilePhone',
    )
    expect(findRule('noId')?.id).toBe('noId')
    expect(findRule('Неизвестный тип')).toBeNull()
  })
})

describe('route', () => {
  test('parseHash', () => {
    expect(parseHash('')).toEqual({ page: 'main' })
    expect(parseHash('#/')).toEqual({ page: 'main' })
    expect(parseHash('#/rules')).toEqual({ page: 'rules' })
    expect(parseHash('#/rules/phone')).toEqual({
      page: 'rules',
      ruleId: 'phone',
    })
    expect(parseHash('#/api/')).toEqual({ page: 'api' })
    expect(parseHash('#/history')).toEqual({ page: 'history' })
    expect(parseHash('#/check/abc')).toEqual({ page: 'check', jobId: 'abc' })
    expect(parseHash('#/demo/report-one')).toEqual({
      page: 'demo',
      state: 'report-one',
    })
    expect(parseHash('#/unknown')).toEqual({ page: 'main' })
  })
})

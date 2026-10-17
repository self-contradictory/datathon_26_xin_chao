function pad(value: number): string {
  return String(value).padStart(2, '0')
}

export function formatTime(totalSeconds: number): string {
  const safe =
    Number.isFinite(totalSeconds) && totalSeconds > 0 ? totalSeconds : 0
  const whole = Math.floor(safe)
  const hours = Math.floor(whole / 3600)
  const minutes = Math.floor((whole % 3600) / 60)
  const seconds = whole % 60
  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`
}

export function formatFrameTime(totalSeconds: number): string {
  const safe =
    Number.isFinite(totalSeconds) && totalSeconds > 0 ? totalSeconds : 0
  const tenths = Math.round(safe * 10)
  return `${formatTime(Math.floor(tenths / 10))}.${tenths % 10}`
}

export interface SizeUnits {
  b: string
  kb: string
  mb: string
  gb: string
}

export function formatFileSize(
  bytes: number,
  locale: string,
  sizeUnits: SizeUnits,
): string {
  const units = [sizeUnits.b, sizeUnits.kb, sizeUnits.mb, sizeUnits.gb]
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1
  return `${value.toLocaleString(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits })} ${units[unit]}`
}

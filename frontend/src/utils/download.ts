export function saveBlob(name: string, blob: Blob): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export function saveFile(name: string, content: string, type: string): void {
  saveBlob(name, new Blob([content], { type }))
}

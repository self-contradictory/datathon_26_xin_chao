export function tabId(prefix: string, key: string): string {
  return `${prefix}-tab-${key}`
}

export function panelId(prefix: string, key: string): string {
  return `${prefix}-panel-${key}`
}

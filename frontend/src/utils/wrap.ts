export function wrapIndex(index: number, by: number, count: number): number {
  return (((index + by) % count) + count) % count
}

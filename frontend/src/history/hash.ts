export const HASH_LIMIT_BYTES = 1024 ** 3

const pending = new WeakMap<Blob, Promise<string | null>>()

async function digest(blob: Blob): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle
  if (!subtle || blob.size > HASH_LIMIT_BYTES) return null
  try {
    const bytes = await subtle.digest('SHA-256', await blob.arrayBuffer())
    return [...new Uint8Array(bytes)]
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('')
  } catch {
    return null
  }
}

export function sha256Hex(blob: Blob): Promise<string | null> {
  const known = pending.get(blob)
  if (known) return known
  const hash = digest(blob)
  pending.set(blob, hash)
  return hash
}

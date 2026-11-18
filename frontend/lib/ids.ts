/**
 * Random URL-safe id (32 hex chars). `crypto.randomUUID` only exists in secure contexts, so
 * it would break when testing on a phone via a LAN IP over plain http; this works everywhere.
 */
export function createId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")
}

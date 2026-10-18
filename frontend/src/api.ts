let token = ''
export async function api<T = any>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  if (method !== 'GET' && !token) token = (await api('/session')).token
  const timeout = AbortSignal.timeout(20000)
  const response = await fetch('/api' + path, { method, signal: signal ? AbortSignal.any([signal, timeout]) : timeout, headers: { 'Content-Type': 'application/json', 'X-Radar-Token': token }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail))
  }
  return response.json()
}
export function stamp(value?: string | null) {
  if (!value) return 'Not yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) + ' IST'
}
export function safeHref(value?: string) {
  try { const u = new URL(value || ''); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : undefined } catch { return undefined }
}

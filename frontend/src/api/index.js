const BASE = '/api'

export async function fetchJSON(url, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`${BASE}${url}?${qs}`)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function postJSON(url, body) {
  const res = await fetch(`${BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function patchJSON(url) {
  const res = await fetch(`${BASE}${url}`, { method: 'PATCH' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// SSE 连接，返回 { close, onMessage }
export function createSSE(url, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const src = new EventSource(`${BASE}${url}?${qs}`)
  return {
    src,
    close: () => src.close(),
    onMessage: (fn) => src.onmessage = (e) => { try { fn(JSON.parse(e.data)) } catch {} },
    onError: (fn) => src.onerror = fn
  }
}

// ── 业务 API ──
export const api = {
  stats: (platform) => fetchJSON('/stats', { platform }),
  jobs: (params) => fetchJSON('/jobs', params),
  config: () => fetchJSON('/config'),
  crawl: (body) => postJSON('/crawl', body),
  apply: (body) => postJSON('/apply', body),
  crawlStatus: () => fetchJSON('/crawl/status'),
  applyStatus: () => fetchJSON('/apply/status'),
  disable: (id, platform) => patchJSON(`/jobs/${id}/disable?platform=${platform}`),
  enable: (id, platform) => patchJSON(`/jobs/${id}/enable?platform=${platform}`),
}

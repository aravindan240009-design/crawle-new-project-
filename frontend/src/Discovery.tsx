import { useEffect, useRef, useState } from 'react'
import { api, stamp } from './api'
import { Badge, External } from './components'

type Row = Record<string, any>
const categories = ['Food', 'Travel', 'Local services', 'Shopping', 'Events', 'Learning', 'Jobs', 'AI', 'Cloud', 'Developer', 'Open source', 'Opportunities']

export function useDiscoveryEvents(onPublish: () => void) {
  const [events, setEvents] = useState<Row[]>([])
  const [connection, setConnection] = useState('Connecting')
  const callback = useRef(onPublish)
  callback.current = onPublish
  useEffect(() => {
    let last = 0
    let disposed = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let stream: EventSource | undefined
    async function connect() {
    const range = await api('/discovery/event-range')
    if (disposed) return
    stream = new EventSource('/api/discovery/stream?after=' + Math.max(0, range.last_id - 150))
    stream.onopen = () => setConnection('Connected · recent history replayed with original times')
    stream.onerror = () => setConnection('Reconnecting · committed events are retained')
    stream.addEventListener('replay_gap', () => setConnection('Connected · older events expired under retention'))
    stream.onmessage = message => {
      try {
        const event = JSON.parse(message.data)
        if (event.id <= last) return
        last = event.id
        setEvents(rows => [...rows, event].slice(-150))
        if (['offer_published', 'offer_updated', 'campaign_completed'].includes(event.stage)) {
          clearTimeout(timer)
          timer = setTimeout(() => callback.current(), 250)
        }
      } catch { setConnection('Unreadable event received; reconnect to replay') }
    }
    }
    connect().catch(() => setConnection('Cannot connect to local event history; reload to retry'))
    return () => { disposed = true; stream?.close(); clearTimeout(timer) }
  }, [])
  return { events, connection }
}

export function Discovery({ events, connection, refresh, onChange }: { events: Row[], connection: string, refresh: number, onChange: () => void }) {
  const [campaigns, setCampaigns] = useState<Row[]>([])
  const [coverage, setCoverage] = useState<Row>({})
  const [caps, setCaps] = useState<Row>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [config, setConfig] = useState({ query_budget: 8, page_budget: 30, seconds: 300, max_depth: 2, per_domain: 5, revisit_minutes: 1440, exploration_share: .2, seeds: true, github: true, browser: false, browser_budget: 2, media_budget: 3, queued_url_budget: 300, byte_budget_mb: 30, disk_limit_mb: 1024, categories })
  const [tab, setTab] = useState('Activity')
  const [rules, setRules] = useState<Row[]>([])
  const [rule, setRule] = useState({ name: '', category: '', location: '', query: '', min_confidence: 65, provisional: false, cooldown_hours: 24 })
  async function reload() {
    const [runs, cov, rules] = await Promise.all([api('/discovery/campaigns'), api('/discovery/coverage'), api('/discovery/rules')])
    setCampaigns(runs); setCoverage(cov); setRules(rules)
  }
  useEffect(() => {
    let pending = false, stopped = false
    async function poll() { if (pending || stopped) return; pending = true; try { await reload() } catch (e) { if (!stopped) setError(String(e)) } finally { pending = false } }
    poll(); api('/discovery/capabilities').then(setCaps).catch(e => setError(String(e)))
    const timer = setInterval(poll, 3000)
    return () => { stopped = true; clearInterval(timer) }
  }, [refresh])
  async function act(path: string, body?: unknown) {
    setBusy(true); setError('')
    try { await api(path, 'POST', body); await reload(); onChange() } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  const active = campaigns.find(c => ['running', 'paused'].includes(c.status))
  const recent = active || campaigns[0]
  const metrics = recent?.metrics || {}
  const query = coverage.queries?.[0]
  return <div className="stack discovery">
    {error && <div className="banner error" role="alert">{error}</div>}
    <section className="surface discovery-hero"><div className="row between"><div><div className="eyebrow">DISCOVER → FETCH → REVIEW</div><h2>A radar that keeps exploring.</h2><p>New domains enter the queue automatically. Provisional results appear immediately; evidence arrives as pages are checked.</p></div><Badge tone={active?.status === 'running' ? 'green' : ''}>{active?.status || 'Ready'}</Badge></div>
      <div className="row"><span className="muted">Budget profile</span>{[{ name: 'Low resource', queries: 3, pages: 8, seconds: 120, media: 0 }, { name: 'Balanced', queries: 8, pages: 30, seconds: 300, media: 3 }, { name: 'Deep discovery', queries: 20, pages: 100, seconds: 900, media: 8 }].map(p => <button key={p.name} onClick={() => setConfig({ ...config, query_budget: p.queries, page_budget: p.pages, seconds: p.seconds, media_budget: p.media })}>{p.name}</button>)}</div>
      <div className="discovery-counts">{[['Queries attempted', metrics.queries_attempted], ['URLs queued', metrics.urls_queued], ['Pages checked', metrics.pages_completed], ['Page failures', metrics.pages_failed]].map(([label, value]) => <div key={label}><strong>{value ?? 0}</strong><span>{label}</span></div>)}</div>
      <div className="row"><button className="primary" disabled={busy || !!active || !config.categories.length} onClick={() => act('/discovery/campaigns', config)}>Start discovery</button>{active && <><button disabled={busy} onClick={() => act(`/discovery/campaigns/${active.id}/${active.status === 'paused' ? 'resume' : 'pause'}`)}>{active.status === 'paused' ? 'Resume' : 'Pause'}</button><button disabled={busy} onClick={() => act(`/discovery/campaigns/${active.id}/cancel`)}>Cancel campaign</button></>}<span className="muted">Runs while this PC is awake and online.</span></div>
      <details><summary>Campaign scope and budgets</summary><div className="settings-grid">{[['query_budget', 'Search queries', 0, 60], ['page_budget', 'Page limit', 1, 500], ['seconds', 'Time limit (seconds)', 10, 3600], ['max_depth', 'Link depth', 0, 5], ['per_domain', 'Pages per domain', 1, 30], ['revisit_minutes', 'Revisit after (minutes)', 15, 43200], ['browser_budget', 'Browser page limit', 0, 20], ['media_budget', 'Media job limit', 0, 30], ['queued_url_budget', 'New URL limit', 10, 3000], ['byte_budget_mb', 'Page body budget (MB)', 2, 500], ['disk_limit_mb', 'Database ceiling (MB)', 50, 10240]].map(([key, label, min, max]) => <label className="field" key={key}>{label}<input type="number" value={config[key as keyof typeof config] as number} min={min} max={max} onChange={e => setConfig({ ...config, [key]: Number(e.target.value) })} /></label>)}</div><div className="discovery-categories">{categories.map(category => <label className="check" key={category}><input type="checkbox" checked={config.categories.includes(category)} onChange={e => setConfig({ ...config, categories: e.target.checked ? [...config.categories, category] : config.categories.filter(c => c !== category) })} />{category}</label>)}</div>{[['seeds', 'Also check seed sources'], ['github', 'Discover GitHub repositories'], ['browser', 'Render JavaScript pages when needed']].map(([key, label]) => <label className="check" key={key}><input type="checkbox" checked={config[key as 'seeds' | 'github' | 'browser']} onChange={e => setConfig({ ...config, [key]: e.target.checked })} />{label}</label>)}<p className="muted">At least 20% of dispatch capacity targets new URLs when available. Remaining capacity revisits known pages.</p></details>
    </section>
    {(query?.status === 'unavailable' || caps.search?.status === 'unavailable') && <div className="banner warning">Broad web search is unavailable. Start the local SearXNG service to enable it. GitHub discovery and permitted links can still run. {query?.diagnostics?.reason}</div>}
    <div className="category-tabs">{['Activity', 'Frontier', 'Coverage', 'Media', 'Capabilities', 'Campaigns', 'Alert rules'].map(t => <button key={t} className={tab === t ? 'chosen' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>
    {tab === 'Alert rules' && <section className="surface"><h2>Local alert rules</h2><p>Matches arrive in Alerts after your IST quiet hours. Provisional discoveries require explicit opt-in.</p><form onSubmit={e => { e.preventDefault(); act('/discovery/rules', rule) }}><div className="settings-grid"><label className="field">Rule name<input required maxLength={100} value={rule.name} onChange={e => setRule({ ...rule, name: e.target.value })} /></label><label className="field">Category<select value={rule.category} onChange={e => setRule({ ...rule, category: e.target.value })}><option value="">Any</option>{categories.map(c => <option key={c}>{c}</option>)}</select></label><label className="field">Location<select value={rule.location} onChange={e => setRule({ ...rule, location: e.target.value })}><option value="">Any / unknown</option><option>Chennai</option><option>Online</option></select></label><label className="field">Contains text<input value={rule.query} onChange={e => setRule({ ...rule, query: e.target.value })} /></label><label className="field">Minimum confidence<input type="number" min="0" max="100" value={rule.min_confidence} onChange={e => setRule({ ...rule, min_confidence: Number(e.target.value) })} /></label><label className="field">Cooldown (hours)<input type="number" min="0" max="8760" value={rule.cooldown_hours} onChange={e => setRule({ ...rule, cooldown_hours: Number(e.target.value) })} /></label></div><label className="check"><input type="checkbox" checked={rule.provisional} onChange={e => setRule({ ...rule, provisional: e.target.checked })} />Allow provisional discoveries</label><button className="primary" disabled={busy}>Create alert rule</button></form>{rules.map(r => <div className="frontier-row" key={r.id}><div><strong>{r.name}</strong><small>{r.category || 'Any category'} · confidence ≥ {r.min_confidence} · {r.cooldown_hours}h cooldown · {r.provisional ? 'Provisional allowed' : 'Reviewed evidence only'}</small></div><button onClick={async () => { try { await api('/discovery/rules/' + r.id, 'DELETE'); await reload() } catch (e) { setError(String(e)) } }}>Delete rule</button></div>)}</section>}
    {tab === 'Activity' && <section className="surface"><div className="row between"><h2>Live activity</h2><span className="muted">{connection}</span></div><p>Persisted events in sequence. Replayed events retain their original timestamps; counters change only when work happens.</p><div className="event-feed" role="log" aria-label="Discovery activity">{!events.length && <p>No activity yet. Start a campaign to see actual work.</p>}{events.slice().reverse().map(e => <div className="event-row" key={e.id}><span className="event-id">#{e.id}</span><div><strong>{e.stage.replaceAll('_', ' ')}</strong><p>{e.resource}</p>{e.code && <p className="event-error">{e.code}</p>}<small>{stamp(e.created)}{e.duration != null && ` · ${e.duration.toFixed(2)}s`}</small></div><details><summary>Details</summary><pre>{JSON.stringify(e.metadata, null, 2)}</pre></details></div>)}</div></section>}
    {tab === 'Frontier' && <section className="surface"><h2>Persistent discovery queue</h2><p>Permission to fetch and issuer trust are assessed separately. A failed fetch does not withdraw an offer.</p>{coverage.frontier_items?.map((r: Row) => <div className="frontier-row" key={r.id}><div><External href={r.url}>{r.url}</External><small>{r.category} · depth {r.depth} · attempt {r.attempts} · policy {r.policy}</small><small>Next eligible: {stamp(r.next_due)} {r.last_error}</small></div><Badge>{r.status}</Badge></div>)}</section>}
    {tab === 'Coverage' && <section className="surface"><h2>Observed coverage</h2><p>These counts describe attempted work, not exhaustive coverage.</p><div className="coverage-grid">{coverage.frontier?.map((r: Row) => <div key={r.category+r.status}><strong>{r.category}</strong><span>{r.count} {r.status}</span></div>)}</div><h3>Search attempts</h3>{coverage.queries?.map((q: Row) => <div className="frontier-row" key={q.id}><div><strong>{q.query}</strong><small>{q.language} · {q.region} · {stamp(q.last_attempt)}</small><small>{q.diagnostics.reason}</small></div><Badge>{q.status}</Badge></div>)}</section>}
    {tab === 'Media' && <section className="surface"><h2>Media evidence queue</h2><p>Permitted direct media only. OCR and speech recognition require local runtimes and language data; extracted text remains unverified evidence.</p>{!coverage.media?.length && <p>No relevant media discovered yet.</p>}{coverage.media?.map((m: Row) => <div className="frontier-row" key={m.id}><div><External href={m.url}>Media source</External><small>{m.language} · {m.error}</small>{m.evidence.map((e: Row, i: number) => <pre key={i}>{e.excerpt}</pre>)}</div><Badge>{m.status}</Badge></div>)}</section>}
    {tab === 'Capabilities' && <section className="surface"><h2>Available on this PC</h2><p>Installed/configured does not mean successfully validated against live sources.</p>{Object.entries(caps).map(([name, value]) => <div className="capability" key={name}><h3>{name.replaceAll('_', ' ')}</h3><pre>{JSON.stringify(value, null, 2)}</pre></div>)}</section>}
    {tab === 'Campaigns' && <section className="stack">{campaigns.map(c => <article className="surface" key={c.id}><div className="row between"><h3>Discovery {c.id.slice(0, 8)}</h3><Badge>{c.status}</Badge></div><p>{stamp(c.created)} · {c.error}</p><p>Already published discoveries survive pause, cancel, failure and interruption.</p>{c.status === 'interrupted' && <button disabled={busy || !!active} onClick={() => act(`/discovery/campaigns/${c.id}/resume`)}>Resume remaining work</button>}<details><summary>Recorded metrics</summary><pre>{JSON.stringify(c.metrics, null, 2)}</pre></details></article>)}</section>}
  </div>
}

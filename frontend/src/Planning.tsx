import { useEffect, useState } from 'react'
import { api, stamp } from './api'
import { Badge, External } from './components'

type Item = Record<string, any>
export const stages = ['interested', 'preparing', 'applied', 'accepted', 'declined', 'archived']

export function TrackingEditor({ itemId, initial, onSaved }: { itemId: string, initial: Item | null, onSaved: () => void }) {
  const [status, setStatus] = useState(initial?.status || 'interested')
  const [date, setDate] = useState(initial?.reminder_date || '')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  return <section className="tracking-editor"><h3>Application tracker</h3><p className="muted">Record your next step. A personal reminder is separate from the official deadline.</p>
    <div className="settings-grid"><label className="field">Application status<select aria-label="Application status" value={status} onChange={e => setStatus(e.target.value)}>{stages.map(s => <option key={s}>{s}</option>)}</select></label><label className="field">Personal reminder date (IST)<input aria-label="Personal reminder date" type="date" value={date} onChange={e => setDate(e.target.value)} /></label></div>
    <button disabled={busy} onClick={async () => { setBusy(true); try { await api('/opportunities/' + itemId + '/tracking', 'PUT', { status, reminder_date: date || null }); setMessage('Tracking saved. Reminders appear in Alerts while Radar is running.'); onSaved() } catch (error) { setMessage(String(error)) } finally { setBusy(false) } }}>Save tracking</button>
    {message && <p role="status">{message}</p>}
  </section>
}

export function Tracker({ refresh, open }: { refresh: number, open: (id: string) => void }) {
  const [items, setItems] = useState<Item[]>([])
  const [stage, setStage] = useState('')
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  useEffect(() => { api('/tracker').then(setItems).catch(e => setError(String(e))) }, [refresh, version])
  return <section className="surface"><div className="row between"><div><h2>Turn discoveries into next steps.</h2><p>Track applications yourself. Radar never applies, registers or redeems on your behalf.</p></div><a href="/api/calendar.ics">Export reminders & exact deadlines (.ics) ↓</a></div>
    {error && <p role="alert">{error}</p>}
    <label className="field">Filter application status<select aria-label="Filter application status" value={stage} onChange={e => setStage(e.target.value)}><option value="">All stages</option>{stages.map(s => <option key={s}>{s}</option>)}</select></label>
    {!items.length && <div className="empty"><h2>No applications tracked yet.</h2><p>Open an opportunity’s evidence and use Application tracker to add a status or personal reminder.</p></div>}
    {items.filter(i => !stage || i.tracking.status === stage).map(item => <article className="tracker-row" key={item.id}><div><Badge>{item.tracking.status}</Badge>{item.stale && <Badge tone="amber">Stale evidence</Badge>}<h3><button className="link-button" onClick={() => open(item.id)}>{item.title}</button></h3><p>{item.tracking.reminder_date ? 'Personal reminder: ' + item.tracking.reminder_date + ' (IST date)' : 'No personal reminder'} · {item.geography}</p><External href={item.official_url}>Official offer</External></div><div className="row"><button onClick={() => open(item.id)}>Update tracking</button><button onClick={async () => { try { await api('/opportunities/' + item.id + '/tracking', 'DELETE'); setVersion(v => v + 1) } catch (error) { setError(String(error)) } }}>Remove from tracker</button></div></article>)}
  </section>
}

export function Digest({ refresh, open }: { refresh: number, open: (id: string) => void }) {
  const [digest, setDigest] = useState<Item | null>(null)
  const [days, setDays] = useState(7)
  const [error, setError] = useState('')
  useEffect(() => { api('/digest?days=' + days).then(setDigest).catch(e => setError(String(e))) }, [refresh, days])
  return <section className="surface"><div className="row between"><div><h2>Your week in opportunities.</h2><p>A local digest of published discoveries, changes and personal reminders.</p></div><a href={'/api/digest/export?days=' + days}>Export digest (.md) ↓</a></div>
    <label className="field">Digest period<select aria-label="Digest period" value={days} onChange={e => setDays(Number(e.target.value))}>{[7, 14, 30].map(n => <option key={n} value={n}>Last {n} days</option>)}</select></label>
    {error && <p role="alert">{error}</p>}
    {!digest && !error && <p role="status">Loading digest…</p>}
    {digest && <><p className="muted">Snapshot: {stamp(digest.snapshot?.published)}. {digest.note}</p>
      <div className="digest-stats"><div><strong>{digest.counts.new}</strong><span>New discoveries</span></div><div><strong>{digest.counts.changes}</strong><span>Material changes</span></div><div><strong>{digest.counts.expiring}</strong><span>Exact deadlines within 7 days</span></div></div>
      {([['new_items', 'New discoveries'], ['expiring', 'Confirmed deadlines approaching']] as const).map(([key, title]) => <section key={key}><h3>{title}</h3>{!digest[key].length && <p className="muted">No matching published opportunities.</p>}{digest[key].map((item: Item) => <article className="digest-row" key={item.id}><button className="link-button" onClick={() => open(item.id)}>{item.title}</button><div className="badges"><Badge>{item.verification}</Badge><Badge>{item.geography}</Badge>{!!item.stale && <Badge tone="amber">Stale evidence</Badge>}</div><p>{item.summary}</p></article>)}</section>)}
      <h3>Material changes</h3>{!digest.changes.length && <p className="muted">No recorded material changes.</p>}{digest.changes.map((change: Item, index: number) => <p key={index}><button className="link-button" onClick={() => open(change.opportunity_id)}>{change.title}</button> · {change.type} · {stamp(change.created)}</p>)}
      <h3>Personal reminders</h3>{!digest.reminders.length && <p className="muted">No personal reminders set.</p>}{digest.reminders.map((item: Item) => <p key={item.id}>{item.tracking.reminder_date} · <button className="link-button" onClick={() => open(item.id)}>{item.title}</button></p>)}
    </>}
  </section>
}

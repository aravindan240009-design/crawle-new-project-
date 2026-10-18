from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from .db import dump
from .extract import collect, canonical_url
from .fetch import Fetcher, FetchError
from .models import Settings, Source, now
from .summary import summarize

LEASE_SECONDS = 90
SUCCESS = {'success', 'unchanged'}


class Busy(Exception):
    pass


def recover(db):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        rows = c.execute("SELECT id FROM scan_runs WHERE status='running' AND heartbeat<?", (time.time() - LEASE_SECONDS,)).fetchall()
        for r in rows:
            c.execute("UPDATE scan_runs SET status='interrupted',finished=?,error='Lease expired; safe retry starts a fresh run' WHERE id=?", (now(), r['id']))
            c.execute('INSERT OR IGNORE INTO alerts(id,type,title,created) VALUES (?,?,?,?)',
                      ('interrupted:' + r['id'], 'scan failure', 'Scan interrupted; last completed snapshot retained', now()))


def acquire(db, mode='full', source_ids=None):
    recover(db)
    settings = db.settings()
    sources = [s for s in db.sources() if s.enabled and (not source_ids or s.id in source_ids)
               and (not settings.source_families or s.family in settings.source_families)]
    if mode == 'incremental':
        health = {r['id']: json.loads(r['health']) for r in db.rows('SELECT id,health FROM sources')}
        current = datetime.now(timezone.utc)
        sources = [s for s in sources if not health[s.id].get('last_attempt') or
                   current - datetime.fromisoformat(health[s.id]['last_attempt']) >= timedelta(minutes=s.cadence_minutes)]
    run_id = uuid.uuid4().hex
    try:
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM campaigns WHERE status IN ('running','paused')").fetchone():
                raise Busy('A discovery campaign is active; finish or cancel it before a seed scan')
            c.execute('INSERT INTO scan_runs(id,status,started,heartbeat,mode,roster,progress,config_snapshot) VALUES (?,?,?,?,?,?,?,?)',
                      (run_id, 'running', now(), time.time(), mode, dump([s.model_dump() for s in sources]),
                       dump({'stage': 'queued', 'completed_sources': 0, 'total_sources': len(sources)}), settings.model_dump_json()))
    except sqlite3.IntegrityError as exc:
        raise Busy('A scan is already running') from exc
    return run_id


def stage_item(db, run_id, source_id, item):
    item.pop('_timings', None)
    identity = canonical_url(item.get('official_url') or item['discovery_url'])
    item_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
    item['id'] = item_id
    # Retrieval times do not create material changes or duplicate alerts.
    semantic = {k: v for k, v in item.items() if k not in ('last_verified', 'evidence', 'provenance', 'model_status')}
    semantic['evidence'] = [{k: v for k, v in e.items() if k not in ('retrieved', 'content_hash')} for e in item['evidence']]
    fingerprint = hashlib.sha256(dump(semantic).encode()).hexdigest()
    version_id = hashlib.sha256((item_id + fingerprint).encode()).hexdigest()[:32]
    with db.connect() as c:
        c.execute('INSERT OR IGNORE INTO opportunities VALUES (?,?,?)', (item_id, identity, now()))
        inserted = c.execute('INSERT OR IGNORE INTO versions VALUES (?,?,?,?,?)', (version_id, item_id, fingerprint, dump(item), now())).rowcount
        if inserted:
            for e in item['evidence']:
                c.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?)', (version_id, e['field'], e['url'], e['excerpt'], e['retrieved'], e['content_hash']))
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='version_search'").fetchone():
                c.execute('INSERT INTO version_search VALUES (?,?,?,?)', (version_id, item['title'], item['summary'], item['provider']))
        c.execute('INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?)', (run_id, source_id, item_id, version_id, dump(item['provenance'])))
    return inserted


def publish(db, run_id, metrics):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        run = c.execute('SELECT * FROM scan_runs WHERE id=?', (run_id,)).fetchone()
        settings = Settings.model_validate_json(run['config_snapshot'])
        if run['status'] != 'running' or run['cancel'] or run['heartbeat'] < time.time() - LEASE_SECONDS:
            raise asyncio.CancelledError()
        states = [r[0] for r in c.execute('SELECT status FROM source_runs WHERE run_id=?', (run_id,))]
        if len(states) != len(json.loads(run['roster'])):
            raise RuntimeError('Cannot publish before every selected source is terminal')
        if not any(s in SUCCESS for s in states):
            c.execute("UPDATE scan_runs SET status='failed',finished=?,metrics=?,error=? WHERE id=?",
                      (now(), dump(metrics), 'No sources successfully checked; previous snapshot retained', run_id))
            c.execute('INSERT OR IGNORE INTO alerts(id,type,title,created) VALUES (?,?,?,?)',
                      ('failure:' + run_id, 'scan failure', 'Scan could not check any source', now()))
            return
        previous = c.execute('SELECT snapshot_id FROM publication WHERE id=1').fetchone()[0]
        previous_versions = {r['opportunity_id']: r['version_id'] for r in c.execute('SELECT * FROM membership WHERE snapshot_id=?', (previous,))}
        c.execute('INSERT INTO snapshots VALUES (?,?)', (run_id, now()))
        if previous:
            selected = [s['id'] for s in json.loads(run['roster'])]
            placeholders = ','.join('?' for _ in selected)
            c.execute('INSERT INTO membership SELECT ?,m.opportunity_id,m.version_id,m.last_seen,CASE WHEN json_extract(v.data,\'$.source_id\') IN (' + placeholders + ') THEN 1 ELSE m.stale END FROM membership m JOIN versions v ON v.id=m.version_id WHERE m.snapshot_id=?', (run_id, *selected, previous))
        for candidate in c.execute('SELECT opportunity_id,version_id FROM candidates WHERE run_id=? ORDER BY source_id', (run_id,)).fetchall():
            oid, vid = candidate
            c.execute('INSERT OR REPLACE INTO membership VALUES (?,?,?,?,0)', (run_id, oid, vid, now()))
            if c.execute('SELECT 1 FROM live_membership WHERE opportunity_id=?', (oid,)).fetchone():
                c.execute('UPDATE live_membership SET version_id=?,last_seen=?,stale=0,campaign_id=? WHERE opportunity_id=?', (vid, now(), run_id, oid))
                from .discovery_store import event
                event(c, run_id, 'offer_updated', metadata={'opportunity_id': oid, 'version_id': vid, 'publication_state': 'legacy_seed_review'})
            item = json.loads(c.execute('SELECT data FROM versions WHERE id=?', (vid,)).fetchone()[0])
            prior = previous_versions.get(oid)
            alert_type = 'new discovery' if not prior else 'material change' if prior != vid else None
            if item['lifecycle'] == 'withdrawn' and prior != vid:
                alert_type = 'withdrawal'
            if settings.alerts_enabled and alert_type and (alert_type != 'new discovery' or item['confidence'] >= settings.min_alert_confidence):
                c.execute('INSERT OR IGNORE INTO alerts(id,opportunity_id,type,title,created) VALUES (?,?,?,?,?)',
                          (f'{oid}:{vid}:{alert_type}', oid, alert_type, item['title'], now()))
            if settings.alerts_enabled and item.get('deadline') and item.get('deadline_precision') == 'instant':
                deadline = datetime.fromisoformat(item['deadline'].replace('Z', '+00:00'))
                if timedelta() <= deadline - datetime.now(timezone.utc) <= timedelta(days=7):
                    c.execute('INSERT OR IGNORE INTO alerts(id,opportunity_id,type,title,created) VALUES (?,?,?,?,?)',
                              (f'{oid}:{vid}:expiry:7d', oid, 'expiring', item['title'], now()))
        status = 'completed' if all(s in SUCCESS for s in states) else 'completed_with_errors'
        if status != 'completed' and settings.alerts_enabled:
            c.execute('INSERT OR IGNORE INTO alerts(id,type,title,created) VALUES (?,?,?,?)',
                      ('coverage:' + run_id, 'low coverage', 'Completed with source errors; inspect coverage', now()))
        c.execute('UPDATE publication SET snapshot_id=? WHERE id=1', (run_id,))
        c.execute('UPDATE scan_runs SET status=?,finished=?,metrics=?,progress=? WHERE id=?',
                  (status, now(), dump(metrics), dump({'stage': 'published', 'completed_sources': len(states), 'total_sources': len(states)}), run_id))


async def execute_run(db, run_id, collector=None, fetcher=None):
    row = db.rows('SELECT * FROM scan_runs WHERE id=?', (run_id,))[0]
    settings = Settings.model_validate_json(row['config_snapshot'])
    if row['status'] != 'running':
        return
    sources = [Source.model_validate(s) for s in json.loads(row['roster'])]
    if not sources:
        db.execute("UPDATE scan_runs SET status='skipped',finished=?,error='No enabled sources due for this roster' WHERE id=?", (now(), run_id))
        return
    fetcher = fetcher or Fetcher(db, settings.concurrency)
    if collector is None and os.environ.get('RADAR_FIXTURES') == '1':
        from .fixtures import fixture_collect
        collector = fixture_collect
    collector = collector or collect
    started = time.perf_counter()
    stages = Counter()
    counts = Counter()
    sem = asyncio.Semaphore(settings.concurrency)
    children = []

    async def heartbeat():
        while True:
            changed = await asyncio.to_thread(db.execute, "UPDATE scan_runs SET heartbeat=? WHERE id=? AND status='running' AND heartbeat>=?", (time.time(), run_id, time.time() - LEASE_SECONDS))
            state = (await asyncio.to_thread(db.rows, 'SELECT cancel,status FROM scan_runs WHERE id=?', (run_id,)))[0]
            if not changed or state['cancel'] or state['status'] != 'running':
                for task in children:
                    task.cancel()
                return
            await asyncio.sleep(1)

    async def process(source):
        async with sem:
            t = time.perf_counter()
            diagnostic = {'started': now(), 'count': 0, 'verified': 0, 'http_status': None}
            try:
                async with asyncio.timeout(min(settings.run_budget_seconds, source.timeout * (source.budget + 2) + 30)):
                    items, page = await collector(source, fetcher)
                    stages['collection_seconds'] += time.perf_counter() - t
                    status = 'unchanged' if page.cached else 'success'
                    diagnostic['http_status'] = page.status
                    for item in items:
                        timings = item.pop('_timings', {})
                        stages.update(timings)
                        counts['verified_candidates'] += item['verification'] == 'Verified'
                        s = time.perf_counter()
                        item['summary'], item['model_status'] = await summarize(item, settings)
                        stages['summary_seconds'] += time.perf_counter() - s
                        s = time.perf_counter()
                        inserted = await asyncio.to_thread(stage_item, db, run_id, source.id, item)
                        if not item.get('official_url'):
                            db.execute('INSERT OR IGNORE INTO leads(id,url,created,notes) VALUES (?,?,?,?)',
                                       (uuid.uuid4().hex, item['discovery_url'], now(), 'Discovered by ' + source.name + '; official domain review needed'))
                        stages['persistence_seconds'] += time.perf_counter() - s
                        counts['candidates'] += 1
                        counts['new_versions'] += inserted
                        diagnostic['count'] += 1
                        diagnostic['verified'] += item['verification'] == 'Verified'
            except asyncio.CancelledError:
                status = 'canceled'
                diagnostic['error'] = 'Canceled or run budget exhausted'
                raise
            except Exception as exc:
                status = getattr(exc, 'status', 'timeout' if isinstance(exc, TimeoutError) else 'failure')
                diagnostic['error'] = str(exc)[:400] or type(exc).__name__
                diagnostic['http_status'] = getattr(exc, 'http_status', None)
            finally:
                diagnostic['duration_seconds'] = round(time.perf_counter() - t, 3)
                diagnostic['finished'] = now()
                db.execute('INSERT OR REPLACE INTO source_runs VALUES (?,?,?,?)', (run_id, source.id, status, dump(diagnostic)))
                old = db.rows('SELECT health FROM sources WHERE id=?', (source.id,))
                health = json.loads(old[0]['health']) if old else {}
                health.update(diagnostic, status=status, last_attempt=diagnostic['started'])
                if status in SUCCESS:
                    health['last_success'] = now()
                    if status == 'success':
                        health['last_change'] = now()
                db.execute('UPDATE sources SET health=? WHERE id=?', (dump(health), source.id))
                completed = db.rows('SELECT count(*) n FROM source_runs WHERE run_id=?', (run_id,))[0]['n']
                db.execute("UPDATE scan_runs SET progress=? WHERE id=? AND status='running'", (dump({'stage': 'collecting and verifying', 'completed_sources': completed, 'total_sources': len(sources)}), run_id))

    beat = asyncio.create_task(heartbeat())
    try:
        children.extend(asyncio.create_task(process(source)) for source in sources)
        async with asyncio.timeout(settings.run_budget_seconds):
            await asyncio.gather(*children)
        stages['total_seconds'] = round(time.perf_counter() - started, 3)
        states = Counter(r['status'] for r in db.rows('SELECT status FROM source_runs WHERE run_id=?', (run_id,)))
        unique = db.rows('SELECT count(DISTINCT opportunity_id) n FROM candidates WHERE run_id=?', (run_id,))[0]['n']
        latencies = sorted(fetcher.latencies)
        metrics = dict(stages, **counts, source_states=dict(states), unique_candidates=unique,
                       duplicate_candidates=counts['candidates'] - unique, cache_hits=fetcher.cache_hits,
                       fetch_count=len(latencies), fetch_p50=latencies[len(latencies)//2] if latencies else None,
                       fetch_p95=latencies[min(len(latencies)-1, int(len(latencies)*.95))] if latencies else None)
        await asyncio.to_thread(publish, db, run_id, metrics)
    except (asyncio.CancelledError, TimeoutError):
        for task in children:
            task.cancel()
        await asyncio.gather(*children, return_exceptions=True)
        db.execute("UPDATE scan_runs SET status='canceled',finished=?,error='Canceled or budget exhausted; previous snapshot retained' WHERE id=? AND status='running'", (now(), run_id))
    except Exception as exc:
        db.execute("UPDATE scan_runs SET status='failed',finished=?,error=? WHERE id=? AND status='running'", (now(), str(exc)[:400], run_id))
        db.execute('INSERT OR IGNORE INTO alerts(id,type,title,created) VALUES (?,?,?,?)', ('failure:' + run_id, 'scan failure', 'Scan failed; previous results retained', now()))
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
        await fetcher.close()

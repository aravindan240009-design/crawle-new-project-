"""Durable discovery state. Each visible version and its event commit together."""
import asyncio
import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from pydantic import Field

from .db import dump
from .extract import canonical_url
from .models import StrictModel, now
from .scanner import Busy, LEASE_SECONDS

CATEGORIES = ['Food', 'Travel', 'Local services', 'Shopping', 'Events', 'Learning',
              'Jobs', 'AI', 'Cloud', 'Developer', 'Open source', 'Opportunities']


class CampaignConfig(StrictModel):
    query_budget: int = Field(default=8, ge=0, le=60)
    page_budget: int = Field(default=30, ge=1, le=500)
    seconds: int = Field(default=300, ge=10, le=3600)
    max_depth: int = Field(default=2, ge=0, le=5)
    per_domain: int = Field(default=5, ge=1, le=30)
    revisit_minutes: int = Field(default=1440, ge=15, le=43200)
    exploration_share: float = Field(default=.2, ge=.2, le=.8)
    seeds: bool = True
    github: bool = True
    browser: bool = False
    browser_budget: int = Field(default=2, ge=0, le=20)
    media_budget: int = Field(default=3, ge=0, le=30)
    queued_url_budget: int = Field(default=300, ge=10, le=3000)
    byte_budget_mb: int = Field(default=30, ge=2, le=500)
    disk_limit_mb: int = Field(default=1024, ge=50, le=10240)
    categories: list[str] = Field(default_factory=lambda: CATEGORIES.copy(), max_length=12)


def event(c, campaign, stage, resource='', metadata=None, task=None, code=None, duration=None):
    def redact(value):
        if isinstance(value, dict):
            return {k: redact(v) for k, v in value.items() if k.lower() not in ('token', 'secret', 'authorization', 'cookie')}
        if isinstance(value, list):
            return [redact(v) for v in value]
        if isinstance(value, str) and value.startswith(('http://', 'https://')):
            u = urlsplit(value)
            return urlunsplit((u.scheme, u.netloc.split('@')[-1], u.path, '[redacted]' if u.query else '', ''))
        return value
    return c.execute('INSERT INTO discovery_events(campaign_id,task_id,created,stage,resource,metadata,code,duration) VALUES (?,?,?,?,?,?,?,?)',
                     (campaign, task, now(), stage, redact(resource), dump(redact(metadata or {})), code, duration)).lastrowid


def emit(db, campaign, stage, resource='', metadata=None, task=None, code=None, duration=None):
    with db.connect() as c:
        return event(c, campaign, stage, resource, metadata, task, code, duration)


def events(db, after=0, campaign=None, limit=200):
    sql, args = 'SELECT * FROM discovery_events WHERE id>?', [after]
    if campaign:
        sql += ' AND campaign_id=?'
        args.append(campaign)
    rows = db.rows(sql + ' ORDER BY id LIMIT ?', (*args, min(limit, 500)))
    return [{**r, 'metadata': json.loads(r['metadata'])} for r in rows]


def recover_campaigns(db):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        for r in c.execute("SELECT id FROM campaigns WHERE status IN ('running','paused') AND heartbeat<?", (time.time()-LEASE_SECONDS,)).fetchall():
            c.execute("UPDATE campaigns SET status='interrupted',error='Worker lease expired; committed discoveries retained' WHERE id=?", (r['id'],))
            c.execute("UPDATE frontier SET status='queued',owner=NULL,lease_until=0 WHERE owner LIKE ?", (r['id'] + ':%',))
            event(c, r['id'], 'campaign_interrupted', code='lease_expired')


def create_campaign(db, config=None):
    recover_campaigns(db)
    config = config or CampaignConfig()
    if not config.categories or any(x not in CATEGORIES for x in config.categories):
        raise ValueError('Choose supported discovery categories')
    cid = uuid.uuid4().hex
    try:
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM scan_runs WHERE status='running'").fetchone():
                raise Busy('A seed scan is running')
            c.execute('INSERT INTO campaigns(id,status,created,heartbeat,config) VALUES (?,?,?,?,?)',
                      (cid, 'running', now(), time.time(), config.model_dump_json()))
            event(c, cid, 'campaign_started', metadata=config.model_dump())
    except sqlite3.IntegrityError as exc:
        raise Busy('A discovery campaign is already active') from exc
    return cid


def campaign_control(db, cid, action):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM campaigns WHERE id=?', (cid,)).fetchone()
        if not row:
            raise ValueError('Campaign not found')
        allowed = {'pause': {'running'}, 'resume': {'paused', 'interrupted'}, 'cancel': {'running', 'paused', 'interrupted'}}
        if action not in allowed or row['status'] not in allowed[action]:
            raise Busy('Campaign cannot perform this transition')
        status = {'pause': 'paused', 'resume': 'running', 'cancel': 'canceled'}[action]
        restart = action == 'resume' and row['status'] == 'interrupted'
        if restart and c.execute("SELECT 1 FROM campaigns WHERE id!=? AND status IN ('running','paused') UNION ALL SELECT 1 FROM scan_runs WHERE status='running'", (cid,)).fetchone():
            raise Busy('Another worker is active')
        c.execute('UPDATE campaigns SET status=?,heartbeat=?,generation=generation+?,finished=?,error=NULL WHERE id=?',
                  (status, time.time(), int(restart), now() if action == 'cancel' else None, cid))
        if action == 'cancel':
            c.execute("UPDATE frontier SET status='queued',owner=NULL,lease_until=0 WHERE owner LIKE ?", (cid + ':%',))
        event(c, cid, 'campaign_' + status)
        return restart


def ensure_worker(c, cid, generation, allow_paused=False):
    row = c.execute('SELECT status,heartbeat,generation FROM campaigns WHERE id=?', (cid,)).fetchone()
    statuses = ('running', 'paused') if allow_paused else ('running',)
    if not row or row['status'] not in statuses or row['generation'] != generation or row['heartbeat'] < time.time()-LEASE_SECONDS:
        raise asyncio.CancelledError()


def queue_url(db, cid, url, parent, category, region='', language='en', depth=0, novel=True, relation='link'):
    url = canonical_url(url)
    u = urlsplit(url)
    if len(url) > 2048 or len(parse_qsl(u.query)) > 6 or len(u.path.split('/')) > 15:
        raise ValueError('URL exceeds crawl-trap budget')
    if any(k.lower() in ('sessionid', 'phpsessid', 'sid', 'token', 'access_token', 'key', 'api_key', 'signature', 'sig') or k.lower().startswith(('x-amz-', 'x-goog-')) for k, _ in parse_qsl(u.query)):
        raise ValueError('Session-bearing or signed URL excluded')
    fid = hashlib.sha256(url.encode()).hexdigest()[:24]
    with db.connect() as c:
        inserted = c.execute('''INSERT OR IGNORE INTO frontier
          (id,url,domain,parent,category,region,language,priority,depth,first_seen,last_seen,next_due,novel)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (fid, url, u.hostname, parent, category, region, language,
          100-depth*10, depth, now(), now(), now(), int(novel))).rowcount
        c.execute('UPDATE frontier SET last_seen=? WHERE id=?', (now(), fid))
        c.execute('INSERT OR IGNORE INTO provenance_edges(child,parent,relation,campaign_id,created) VALUES (?,?,?,?,?)', (url, parent, relation, cid, now()))
        c.execute('INSERT OR IGNORE INTO entities(id,domain,name,first_seen,last_seen) VALUES (?,?,?,?,?)', (hashlib.sha256(u.hostname.encode()).hexdigest()[:24], u.hostname, u.hostname, now(), now()))
        if inserted:
            event(c, cid, 'url_queued', url, {'parent': parent, 'depth': depth, 'category': category, 'novel': novel}, fid)
    return fid, bool(inserted)


def claim_task(db, cid, generation, config, want_novel, domain_counts, category_counts=None):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        ensure_worker(c, cid, generation)
        c.execute("UPDATE frontier SET status='queued',owner=NULL WHERE status='fetching' AND lease_until<?", (time.time(),))
        rows = c.execute("SELECT * FROM frontier WHERE status IN ('queued','visited','retry') AND next_due<=? AND depth<=? ORDER BY (novel=?) DESC,priority DESC,next_due LIMIT 1000", (now(), config.max_depth, int(want_novel))).fetchall()
        if category_counts is not None:
            rows = sorted(rows, key=lambda r: (r['novel'] != int(want_novel), category_counts.get(r['category'], 0), -r['priority'], r['next_due']))
        for row in rows:
            if row['category'] not in config.categories or domain_counts.get(row['domain'], 0) >= config.per_domain:
                continue
            owner = f'{cid}:{generation}'
            c.execute("UPDATE frontier SET status='fetching',owner=?,lease_until=?,attempts=attempts+1 WHERE id=?", (owner, time.time()+LEASE_SECONDS, row['id']))
            event(c, cid, 'task_leased', row['url'], {'attempt': row['attempts']+1}, row['id'])
            return dict(row)
    return None


def finish_task(db, cid, generation, task, config, error=None, size=0):
    due = (datetime.now(timezone.utc)+timedelta(minutes=min(1440, 15*2**min(task['attempts'], 6)) if error else config.revisit_minutes)).isoformat()
    with db.connect() as c:
        count = c.execute('UPDATE frontier SET status=?,next_due=?,last_error=?,bytes=?,policy=?,owner=NULL,lease_until=0,novel=? WHERE id=? AND owner=?',
          ('retry' if error else 'visited', due, error, size, 'not_confirmed' if error else 'robots_allowed', int(bool(error) and task['novel']), task['id'], f'{cid}:{generation}')).rowcount
        if count:
            if error:
                previous = c.execute('SELECT * FROM current_membership WHERE opportunity_id=?', (task['id'],)).fetchone()
                if previous:
                    c.execute('INSERT OR REPLACE INTO live_membership VALUES (?,?,?,1,?)', (task['id'], previous['version_id'], previous['last_seen'], cid))
            event(c, cid, 'task_failed' if error else 'task_completed', task['url'], {'bytes': size, 'next_due': due}, task['id'], code=error)


def commit_live(db, cid, generation, item):
    settings = db.settings()
    item = dict(item)
    item.pop('_timings', None)
    url = canonical_url(item.get('official_url') or item['discovery_url'])
    oid = hashlib.sha256(url.encode()).hexdigest()[:24]
    item['id'] = oid
    semantic = {k: v for k, v in item.items() if k not in ('last_verified', 'evidence', 'provenance', 'model_status', 'observation_time')}
    semantic['evidence'] = [{k: v for k, v in e.items() if k not in ('retrieved', 'content_hash')} for e in item['evidence']]
    fingerprint = hashlib.sha256(dump(semantic).encode()).hexdigest()
    vid = hashlib.sha256((oid+fingerprint).encode()).hexdigest()[:32]
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        ensure_worker(c, cid, generation)
        previous = c.execute('SELECT version_id FROM current_membership WHERE opportunity_id=?', (oid,)).fetchone()
        # Search rediscovery cannot replace an already fetched evidence version.
        if previous and item['publication_state'] == 'provisional':
            return oid
        c.execute('INSERT OR IGNORE INTO opportunities VALUES (?,?,?)', (oid, url, now()))
        inserted = c.execute('INSERT OR IGNORE INTO versions VALUES (?,?,?,?,?)', (vid, oid, fingerprint, dump(item), now())).rowcount
        if inserted:
            for e in item['evidence']:
                c.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?)', (vid, e['field'], e['url'], e['excerpt'], e['retrieved'], e['content_hash']))
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='version_search'").fetchone():
                c.execute('INSERT INTO version_search VALUES (?,?,?,?)', (vid, item['title'], item['summary'], item['provider']))
        c.execute('INSERT OR REPLACE INTO live_membership VALUES (?,?,?,0,?)', (oid, vid, now(), cid))
        c.execute('INSERT OR IGNORE INTO live_versions VALUES (?,?,?,?,?)', (vid, oid, cid, now(), item['publication_state']))
        changed = not previous or previous['version_id'] != vid
        if changed:
            from .discovery_alerts import match_rules
            c.execute("DELETE FROM pending_alerts WHERE opportunity_id=? AND type='deadline reminder'", (oid,))
            match_rules(c, item, vid, settings)
            event(c, cid, 'offer_published' if not previous else 'offer_updated', url,
                  {'opportunity_id': oid, 'version_id': vid, 'publication_state': item['publication_state'], 'verification': item['verification']})
        return oid


def finish_campaign(db, cid, generation, metrics, error=None):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        ensure_worker(c, cid, generation)
        status = 'failed' if error else 'completed_with_errors' if metrics.get('pages_failed') or metrics.get('queries_failed') else 'completed'
        # Archive a point-in-time copy. This never gates live visibility.
        c.execute('INSERT INTO scan_runs(id,status,started,finished,heartbeat,mode,roster,metrics,config_snapshot) SELECT id,?,created,?,?,?,\'[]\',?,config FROM campaigns WHERE id=?',
                  ('completed_with_errors' if error or status == 'completed_with_errors' else 'completed', now(), time.time(), 'discovery archive', dump(metrics), cid))
        c.execute('INSERT INTO snapshots VALUES (?,?)', (cid, now()))
        c.execute('INSERT INTO membership SELECT ?,opportunity_id,version_id,last_seen,stale FROM current_membership', (cid,))
        c.execute('UPDATE publication SET snapshot_id=? WHERE id=1', (cid,))
        c.execute('UPDATE campaigns SET status=?,finished=?,metrics=?,error=? WHERE id=?', (status, now(), dump(metrics), error, cid))
        event(c, cid, 'campaign_' + status, metadata=metrics, code=error)


def campaign_rows(db):
    return [{**r, 'config': json.loads(r['config']), 'metrics': json.loads(r['metrics'])}
            for r in db.rows('SELECT * FROM campaigns ORDER BY created DESC LIMIT 50')]

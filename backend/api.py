from __future__ import annotations

import asyncio
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .db import Database, ROOT, dump
from .fetch import validate_url, FetchError
from .models import Filters, ItemState, Settings, Source, StrictModel, Tracking, now
from .planning import tracked_items, weekly_digest, digest_markdown, calendar_export, reminder_alerts
from .query import query_results, csv_export
from .scanner import Busy, acquire, execute_run, recover
from .scheduler import loop, next_time
from .discovery_api import install_routes
from .discovery_store import recover_campaigns


class StartScan(StrictModel):
    mode: Literal['full', 'incremental'] = 'full'
    source_ids: list[str] = Field(default_factory=list, max_length=100)


class SavedView(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    filters: Filters


class Lead(StrictModel):
    url: str = Field(max_length=2048)
    notes: str = Field(default='', max_length=2000)


class AlertState(StrictModel):
    read: bool = True
    resolved: bool = False


def create_app(db=None):
    db = db or Database()
    tasks = set()
    token = secrets.token_urlsafe(32)
    port = os.environ.get('RADAR_PORT', '8765')
    allowed = {f'http://127.0.0.1:{port}', f'http://localhost:{port}', 'http://127.0.0.1:5173', 'http://localhost:5173'}

    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        recover(db)
        recover_campaigns(db)
        scheduler = asyncio.create_task(loop(db, tasks))
        yield
        scheduler.cancel()
        for task in tuple(tasks):
            task.cancel()
        await asyncio.gather(scheduler, *tuple(tasks), return_exceptions=True)

    app = FastAPI(title='Global Opportunity Radar', version='0.1.0', lifespan=lifespan,
                  docs_url='/api/docs', openapi_url='/api/openapi.json', redoc_url=None)
    app.state.db = db
    install_routes(app, db, tasks)

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        host = request.headers.get('host', '').split(':')[0]
        if host not in ('127.0.0.1', 'localhost', 'testserver'):
            return JSONResponse({'detail': 'Host is not allowed'}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin not in allowed:
            return JSONResponse({'detail': 'Origin is not allowed'}, status_code=403)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.headers.get('sec-fetch-site') == 'cross-site' or not secrets.compare_digest(request.headers.get('x-radar-token', ''), token):
                return JSONResponse({'detail': 'Missing or invalid local session token; reload dashboard'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api') else 'no-cache'
        return response

    @app.exception_handler(Busy)
    async def busy_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.get('/api/session')
    def session():
        return {'token': token, 'demo': os.environ.get('RADAR_FIXTURES') == '1'}

    @app.get('/api/health')
    @app.get('/api/ready')
    def health():
        db.rows('SELECT 1')
        return {'status': 'ok', 'database': 'ready'}

    @app.get('/api/status')
    def status():
        recover(db)
        current = db.rows("SELECT * FROM scan_runs WHERE status='running'")
        last = db.rows('SELECT * FROM scan_runs ORDER BY started DESC LIMIT 1')
        completed = db.rows('SELECT r.* FROM publication p JOIN scan_runs r ON r.id=p.snapshot_id WHERE p.id=1')
        schedule = db.rows('SELECT * FROM schedule WHERE id=1')[0]
        beat = schedule['worker_heartbeat']
        schedule['worker_running'] = bool(beat and datetime.fromisoformat(beat) > datetime.now(timezone.utc) - timedelta(seconds=35))
        def parse(row):
            if not row:
                return None
            r = row[0]
            for key in ('roster', 'progress', 'metrics'):
                r[key] = json.loads(r[key])
            return r
        return {'current': parse(current), 'last_attempt': parse(last), 'last_completed': parse(completed), 'schedule': schedule}

    @app.post('/api/scans', status_code=202)
    async def start(body: StartScan):
        run_id = acquire(db, body.mode, body.source_ids)
        task = asyncio.create_task(execute_run(db, run_id))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return {'id': run_id}

    @app.get('/api/scans')
    def scans():
        return [{**r, 'metrics': json.loads(r['metrics']), 'progress': json.loads(r['progress']), 'roster': json.loads(r['roster']),
                 'sources': [{**s, 'diagnostics': json.loads(s['diagnostics'])} for s in db.rows('SELECT * FROM source_runs WHERE run_id=?', (r['id'],))]}
                for r in db.rows('SELECT * FROM scan_runs ORDER BY started DESC LIMIT 100')]

    @app.post('/api/scans/{run_id}/cancel')
    def cancel(run_id: str):
        if not db.execute("UPDATE scan_runs SET cancel=1 WHERE id=? AND status='running'", (run_id,)):
            raise HTTPException(409, 'Run is no longer active')
        return {'status': 'cancel_requested'}

    @app.get('/api/results')
    def results(filters: Annotated[Filters, Query()]):
        return query_results(db, filters)

    @app.get('/api/export/{format}')
    def export(format: Literal['json', 'csv'], filters: Annotated[Filters, Query()]):
        result = query_results(db, filters, export=True)
        content = dump(result) if format == 'json' else csv_export(result['items'])
        return Response(content, media_type='application/json' if format == 'json' else 'text/csv',
                        headers={'Content-Disposition': f'attachment; filename="opportunities.{format}"'})

    @app.get('/api/opportunities/{item_id}')
    def detail(item_id: str, snapshot: str = ''):
        snap = snapshot or db.rows('SELECT snapshot_id FROM publication WHERE id=1')[0]['snapshot_id']
        rows = db.rows('SELECT v.* FROM membership m JOIN versions v ON v.id=m.version_id WHERE m.snapshot_id=? AND m.opportunity_id=?', (snap, item_id)) if snapshot else db.rows('SELECT v.* FROM current_membership m JOIN versions v ON v.id=m.version_id WHERE m.opportunity_id=?', (item_id,))
        if not rows:
            raise HTTPException(404, 'Opportunity is not in this published snapshot')
        item = json.loads(rows[0]['data'])
        item['version_id'] = rows[0]['id']
        item['state'] = (db.rows('SELECT bookmarked,dismissed,notes FROM item_state WHERE opportunity_id=?', (item_id,)) or [ItemState().model_dump()])[0]
        item['tracking'] = (db.rows('SELECT status,reminder_date,updated FROM item_tracking WHERE opportunity_id=?', (item_id,)) or [None])[0]
        history = db.rows('SELECT DISTINCT v.id,v.created,v.data FROM versions v JOIN membership m ON m.version_id=v.id JOIN snapshots s ON s.id=m.snapshot_id WHERE v.opportunity_id=? AND s.published<=(SELECT published FROM snapshots WHERE id=?) ORDER BY v.created', (item_id, snap))
        if not snapshot:
            live_history = db.rows('SELECT v.id,v.created,v.data FROM versions v JOIN live_versions l ON l.version_id=v.id WHERE v.opportunity_id=?', (item_id,))
            history = sorted({h['id']: h for h in history + live_history}.values(), key=lambda h: h['created'])
        prev = {}
        entries = []
        for h in history:
            facts = json.loads(h['data'])
            changes = {k: {'before': prev.get(k), 'after': facts.get(k)} for k in ('benefit', 'geography', 'restrictions', 'deadline', 'verification', 'lifecycle', 'card_required') if facts.get(k) != prev.get(k)}
            entries.append({'id': h['id'], 'created': h['created'], 'changes': changes})
            prev = facts
        item['history'] = entries
        item['provenance'] = [json.loads(r['provenance']) for r in db.rows('SELECT DISTINCT c.provenance FROM candidates c JOIN snapshots s ON s.id=c.run_id WHERE c.opportunity_id=? AND s.published<=(SELECT published FROM snapshots WHERE id=?)', (item_id, snap))]
        if not snapshot:
            item['provenance'].extend(db.rows('SELECT parent,child,relation,created FROM provenance_edges WHERE child=?', (item.get('official_url') or item['discovery_url'],)))
            item['media_evidence'] = [{**r, 'evidence': json.loads(r['evidence'])} for r in db.rows('SELECT * FROM media_jobs WHERE frontier_id=?', (item_id,))]
        return item

    @app.put('/api/opportunities/{item_id}/state')
    def state(item_id: str, body: ItemState):
        if not db.rows('SELECT 1 FROM membership WHERE opportunity_id=? UNION ALL SELECT 1 FROM live_membership WHERE opportunity_id=?', (item_id, item_id)):
            raise HTTPException(404, 'No published opportunity')
        db.execute('INSERT OR REPLACE INTO item_state VALUES (?,?,?,?)', (item_id, body.bookmarked, body.dismissed, body.notes))
        return body

    @app.get('/api/sources')
    def sources():
        return [{**json.loads(r['config']), 'health': json.loads(r['health'])} for r in db.rows('SELECT * FROM sources ORDER BY id')]

    @app.get('/api/tracker')
    def tracker():
        return tracked_items(db)

    @app.put('/api/opportunities/{item_id}/tracking')
    def track(item_id: str, body: Tracking):
        if not db.rows('SELECT 1 FROM membership WHERE opportunity_id=? UNION ALL SELECT 1 FROM live_membership WHERE opportunity_id=?', (item_id, item_id)):
            raise HTTPException(404, 'No published opportunity')
        db.execute('INSERT INTO item_tracking VALUES (?,?,?,?) ON CONFLICT(opportunity_id) DO UPDATE SET status=excluded.status,reminder_date=excluded.reminder_date,updated=excluded.updated',
                   (item_id, body.status, body.reminder_date, now()))
        reminder_alerts(db)
        return body

    @app.delete('/api/opportunities/{item_id}/tracking')
    def untrack(item_id: str):
        db.execute('DELETE FROM item_tracking WHERE opportunity_id=?', (item_id,))
        return {'removed': True}

    @app.get('/api/digest')
    def digest(days: int = Query(default=7, ge=1, le=90)):
        return weekly_digest(db, days)

    @app.get('/api/digest/export')
    def export_digest(days: int = Query(default=7, ge=1, le=90)):
        return Response(digest_markdown(weekly_digest(db, days)), media_type='text/markdown',
                        headers={'Content-Disposition': 'attachment; filename="opportunity-digest.md"'})

    @app.get('/api/calendar.ics')
    def calendar():
        return Response(calendar_export(db), media_type='text/calendar',
                        headers={'Content-Disposition': 'attachment; filename="radar-calendar.ics"'})

    @app.put('/api/sources/{source_id}')
    def save_source(source_id: str, body: Source):
        if source_id != body.id:
            raise HTTPException(422, 'Source ID must match')
        try:
            validate_url(body.url)
            if body.terms_url:
                validate_url(body.terms_url)
        except (ValueError, FetchError) as exc:
            raise HTTPException(422, str(exc)) from exc
        db.execute("INSERT INTO sources(id,config) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config", (source_id, body.model_dump_json()))
        return body

    @app.get('/api/settings')
    def settings():
        return db.settings()

    @app.put('/api/settings')
    def save_settings(body: Settings):
        with db.connect() as c:
            c.execute('UPDATE settings SET value=? WHERE id=1', (body.model_dump_json(),))
            c.execute('UPDATE schedule SET next_run=? WHERE id=1', (next_time(body),))
        return body

    @app.get('/api/alerts')
    def alerts():
        return db.rows('SELECT * FROM alerts ORDER BY created DESC LIMIT 300')

    @app.put('/api/alerts/{alert_id}')
    def alert(alert_id: str, body: AlertState):
        db.execute('UPDATE alerts SET read=?,resolved=? WHERE id=?', (body.read, body.resolved, alert_id))
        return body

    @app.get('/api/views')
    def views():
        return [{**r, 'filters': json.loads(r['filters'])} for r in db.rows('SELECT * FROM saved_views')]

    @app.post('/api/views')
    def save_view(body: SavedView):
        view_id = uuid.uuid4().hex
        db.execute('INSERT INTO saved_views VALUES (?,?,?)', (view_id, body.name, body.filters.model_dump_json()))
        return {'id': view_id}

    @app.delete('/api/views/{view_id}')
    def delete_view(view_id: str):
        db.execute('DELETE FROM saved_views WHERE id=?', (view_id,))
        return {'deleted': True}

    @app.get('/api/leads')
    def leads():
        return db.rows('SELECT * FROM leads ORDER BY created DESC')

    @app.post('/api/leads')
    def add_lead(body: Lead):
        try:
            from .discovery_store import queue_url
            queue_url(db, None, body.url, 'user_submission', 'Opportunities', relation='submitted_lead')
        except Exception as exc:
            raise HTTPException(422, str(exc)) from exc
        db.execute('INSERT OR IGNORE INTO leads(id,url,created,notes) VALUES (?,?,?,?)', (uuid.uuid4().hex, body.url, now(), body.notes))
        db.execute("UPDATE leads SET status='queued' WHERE url=?", (body.url,))
        return {'status': 'queued', 'message': 'Queued for a discovery campaign; issuer identity remains unassessed'}

    @app.post('/api/maintenance/retention')
    def retention():
        cutoff = (datetime.now(timezone.utc) - timedelta(days=db.settings().retention_days)).isoformat()
        count = db.execute('DELETE FROM fetch_cache WHERE fetched<?', (cutoff,))
        event_cutoff = (datetime.now(timezone.utc) - timedelta(days=db.settings().event_retention_days)).isoformat()
        deleted_events = db.execute("DELETE FROM discovery_events WHERE created<? AND campaign_id IN (SELECT id FROM campaigns WHERE status IN ('completed','completed_with_errors','failed','canceled'))", (event_cutoff,))
        return {'cache_entries_deleted': count, 'events_deleted': deleted_events, 'note': 'Immutable published evidence and user history retained; active/interrupted campaign events retained for resume'}

    build = ROOT / 'frontend/dist'
    if build.exists():
        app.mount('/assets', StaticFiles(directory=build / 'assets'), name='assets')

    @app.get('/')
    def index():
        if (build / 'index.html').exists():
            return FileResponse(build / 'index.html')
        return JSONResponse({'detail': 'Frontend not built. Run setup commands in README.md.'}, status_code=503)

    return app


app = create_app()

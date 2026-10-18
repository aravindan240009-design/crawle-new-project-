import asyncio
import json
import uuid
from typing import Literal

from fastapi import HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .db import dump
from .discovery import run_campaign
from .discovery_media import media_capabilities
from .discovery_alerts import Rule, list_rules, save_rule
from .discovery_store import (CampaignConfig, campaign_control, campaign_rows, create_campaign,
                             events, recover_campaigns)


def install_routes(app, db, tasks):
    def launch(cid):
        task = asyncio.create_task(run_campaign(db, cid))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.get('/api/discovery/rules')
    def rules():
        return list_rules(db)

    @app.post('/api/discovery/rules', status_code=201)
    def add_rule(body: Rule):
        rid = uuid.uuid4().hex
        save_rule(db, rid, body)
        return {'id': rid}

    @app.delete('/api/discovery/rules/{rid}')
    def remove_rule(rid: str):
        with db.connect() as c:
            c.execute('DELETE FROM alert_rules WHERE id=?', (rid,))
            c.execute('DELETE FROM pending_alerts WHERE id LIKE ?', ('rule:' + rid + ':%',))
        return {'removed': True}

    @app.post('/api/discovery/campaigns', status_code=202)
    async def start(body: CampaignConfig):
        try:
            cid = await asyncio.to_thread(create_campaign, db, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        launch(cid)
        return {'id': cid}

    @app.get('/api/discovery/campaigns')
    def campaigns():
        recover_campaigns(db)
        return campaign_rows(db)

    @app.post('/api/discovery/campaigns/{cid}/{action}')
    async def control(cid: str, action: Literal['pause', 'resume', 'cancel']):
        try:
            restart = await asyncio.to_thread(campaign_control, db, cid, action)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        if restart:
            launch(cid)
        return {'action': action, 'restarted': restart}

    @app.get('/api/discovery/events')
    def event_history(after: int = Query(0, ge=0), campaign: str = '', limit: int = Query(200, ge=1, le=500)):
        return events(db, after, campaign or None, limit)

    @app.get('/api/discovery/stream')
    async def stream(request: Request, after: int = Query(0, ge=0)):
        try:
            cursor = max(after, int(request.headers.get('last-event-id', '0')))
        except ValueError:
            raise HTTPException(422, 'Invalid event cursor')
        async def frames():
            nonlocal cursor
            yield 'retry: 2000\n\n'
            earliest = (await asyncio.to_thread(db.rows, 'SELECT min(id) id FROM discovery_events'))[0]['id']
            if cursor and earliest and cursor < earliest-1:
                yield 'event: replay_gap\ndata: ' + dump({'first_retained_id': earliest, 'reason': 'Older events were removed by configured retention'}) + '\n\n'
            while not await request.is_disconnected():
                rows = await asyncio.to_thread(events, db, cursor)
                if rows:
                    for row in rows:
                        cursor = row['id']
                        yield f'id: {cursor}\ndata: {dump(row)}\n\n'
                else:
                    # Transport keepalive only; never stored/countable activity.
                    yield ': keepalive\n\n'
                    await asyncio.sleep(1)
        return StreamingResponse(frames(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})

    @app.get('/api/discovery/event-range')
    def event_range():
        return db.rows('SELECT coalesce(min(id),0) first_id,coalesce(max(id),0) last_id FROM discovery_events')[0]

    @app.get('/api/discovery/coverage')
    def coverage():
        return {'frontier': db.rows('SELECT category,status,count(*) count FROM frontier GROUP BY category,status'),
                'domains': db.rows('SELECT domain,count(*) pages,sum(status=\'visited\') visited FROM frontier GROUP BY domain ORDER BY pages DESC LIMIT 100'),
                'queries': [{**r, 'diagnostics': json.loads(r['diagnostics'] or '{}')} for r in db.rows('SELECT * FROM queries WHERE last_attempt IS NOT NULL ORDER BY last_attempt DESC LIMIT 60')],
                'frontier_items': db.rows('SELECT * FROM frontier ORDER BY last_seen DESC LIMIT 80'),
                'media': [{**r, 'evidence': json.loads(r['evidence'])} for r in db.rows('SELECT * FROM media_jobs ORDER BY created DESC LIMIT 40')],
                'last_event_id': db.rows('SELECT coalesce(max(id),0) id FROM discovery_events')[0]['id']}

    @app.get('/api/discovery/capabilities')
    def capabilities():
        import importlib.util
        from pathlib import Path
        browser_available = False
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser_available = Path(p.chromium.executable_path).is_file()
        except Exception:
            pass
        search = db.rows("SELECT status,diagnostics,last_attempt FROM queries WHERE engine='searxng' AND last_attempt IS NOT NULL ORDER BY last_attempt DESC LIMIT 1")
        return {'crawlee': {'installed': importlib.util.find_spec('crawlee') is not None, 'mode': 'BasicCrawler with connection-pinned Fetcher; no evasion'},
                'browser': {'available': browser_available, 'enabled_by_default': False},
                'search': {'endpoint': 'http://127.0.0.1:8088', 'status': search[0]['status'] if search else 'not_checked',
                           'last_attempt': search[0]['last_attempt'] if search else None,
                           'detail': json.loads(search[0]['diagnostics'] or '{}') if search else {}},
                **media_capabilities()}

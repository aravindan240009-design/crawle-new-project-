import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import now
from .scanner import acquire, execute_run, recover, Busy
from .planning import reminder_alerts

ZONE = ZoneInfo('Asia/Kolkata')


def next_time(settings, current=None):
    current = current or datetime.now(timezone.utc)
    if not settings.armed or settings.mode == 'manual':
        return None
    if settings.mode == 'continuous':
        return (current + timedelta(minutes=settings.continuous_minutes)).isoformat()
    hour, minute = map(int, settings.daily_time.split(':'))
    local = current.astimezone(ZONE)
    nxt = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nxt <= local:
        nxt += timedelta(days=1)
    return nxt.astimezone(timezone.utc).isoformat()


def tick(db):
    recover(db)
    from .discovery_store import recover_campaigns
    recover_campaigns(db)
    settings = db.settings()
    due = False
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM schedule WHERE id=1').fetchone()
        current = now()
        c.execute('UPDATE schedule SET worker_heartbeat=? WHERE id=1', (current,))
        if not settings.armed or settings.mode == 'manual':
            c.execute('UPDATE schedule SET next_run=NULL WHERE id=1')
        elif not row['next_run']:
            c.execute('UPDATE schedule SET next_run=? WHERE id=1', (next_time(settings),))
        elif row['next_run'] <= current:
            due = True
            c.execute('UPDATE schedule SET next_run=? WHERE id=1', (next_time(settings),))
    reminder_alerts(db)
    from .discovery_alerts import deliver_pending
    deliver_pending(db)
    return settings, due


async def loop(db, tasks):
    while True:
        settings, due = await asyncio.to_thread(tick, db)
        if due:
            try:
                if settings.discovery_enabled:
                    from .discovery_store import create_campaign, CampaignConfig
                    from .discovery import run_campaign
                    run = await asyncio.to_thread(create_campaign, db, CampaignConfig(seconds=settings.run_budget_seconds))
                    task = asyncio.create_task(run_campaign(db, run))
                else:
                    run = await asyncio.to_thread(acquire, db, 'incremental' if settings.mode == 'continuous' else 'full')
                    task = asyncio.create_task(execute_run(db, run))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            except Busy:
                pass
        await asyncio.sleep(10)

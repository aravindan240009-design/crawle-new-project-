import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api import create_app
from backend.db import Database
from backend.fixtures import fixture_collect
from backend.models import Tracking, now
from backend.planning import calendar_export, digest_markdown, reminder_alerts, tracked_items, weekly_digest
from backend.scanner import acquire, execute_run, stage_item


async def completed(db):
    run = acquire(db)
    await execute_run(db, run, collector=fixture_collect)
    return run


async def test_digest_excludes_staging_news_ineligible_and_dismissed(db):
    assert weekly_digest(db)['counts']['new'] == 0
    await completed(db)
    digest = weekly_digest(db)
    assert len(digest['new_items']) == 2
    oid = digest['new_items'][0]['id']
    db.execute('INSERT INTO item_state VALUES (?,0,1,?)', (oid, 'dismissed'))
    assert len(weekly_digest(db)['new_items']) == 1
    run = acquire(db)
    items, _ = await fixture_collect(db.sources()[0], None)
    items[0]['title'] = 'Unpublished staged title'
    stage_item(db, run, db.sources()[0].id, items[0])
    assert 'Unpublished staged title' not in digest_markdown(weekly_digest(db))


async def test_digest_changes_do_not_depend_on_alert_settings(db):
    await completed(db)
    settings = db.settings().model_copy(update={'alerts_enabled': False})
    db.execute('UPDATE settings SET value=?', (settings.model_dump_json(),))
    async def changed(source, fetcher):
        items, page = await fixture_collect(source, fetcher)
        items[0]['benefit'] = 'Changed supported benefit'
        return items, page
    run = acquire(db)
    await execute_run(db, run, collector=changed)
    changes = weekly_digest(db)['changes']
    assert len(changes) == 2  # Confirmed geographic exclusion still hidden.
    assert all(c['type'] == 'material change' for c in changes)


async def test_tracking_survives_versions_and_restart(db):
    await completed(db)
    oid = weekly_digest(db)['new_items'][0]['id']
    db.execute('INSERT INTO item_tracking VALUES (?,?,?,?)', (oid, 'preparing', '2027-01-03', now()))
    await completed(db)
    restored = Database(db.path)
    item = tracked_items(restored)[0]
    assert item['tracking']['status'] == 'preparing'
    assert item['tracking']['reminder_date'] == '2027-01-03'
    assert item['deadline'] is None
    calendar = calendar_export(db)
    assert 'DTSTART;VALUE=DATE:20270103' in calendar
    assert 'Personal Reminder:' in calendar
    assert 'Official Deadline:' not in calendar
    assert [line for line in calendar.splitlines() if line.startswith('UID:')] == [line for line in calendar_export(db).splitlines() if line.startswith('UID:')]


async def test_due_reminders_ist_dedup_and_closed_status(db):
    await completed(db)
    oid = weekly_digest(db)['new_items'][0]['id']
    db.execute('INSERT INTO item_tracking VALUES (?,?,?,?)', (oid, 'applied', '2026-10-10', now()))
    # UTC evening is already the next calendar date in India.
    current = datetime(2026, 10, 9, 19, tzinfo=timezone.utc)
    reminder_alerts(db, current)
    reminder_alerts(db, current)
    assert len(db.rows("SELECT * FROM alerts WHERE type='personal reminder'")) == 1
    db.execute("UPDATE item_tracking SET status='accepted',reminder_date='2026-10-11'")
    reminder_alerts(db, current + timedelta(days=5))
    assert len(db.rows("SELECT * FROM alerts WHERE type='personal reminder'")) == 1
    assert 'BEGIN:VEVENT' not in calendar_export(db)


@pytest.mark.parametrize('date', ['2026-02-30', '2026-1-01', 'tomorrow', '2026-10-09T10:00:00Z'])
def test_personal_date_validation(date):
    with pytest.raises(ValidationError):
        Tracking(reminder_date=date)


def test_tracker_api_security_validation_and_export(db):
    asyncio.run(completed(db))
    with TestClient(create_app(db)) as client:
        oid = client.get('/api/results').json()['items'][0]['id']
        path = '/api/opportunities/' + oid + '/tracking'
        assert client.put(path, json={'status': 'applied'}).status_code == 403
        headers = {'X-Radar-Token': client.get('/api/session').json()['token']}
        assert client.put(path, json={'status': 'auto-apply'}, headers=headers).status_code == 422
        assert client.put(path, json={'status': 'preparing', 'reminder_date': '2027-01-02'}, headers=headers).status_code == 200
        assert client.get('/api/tracker').json()[0]['id'] == oid
        assert client.get('/api/digest?days=999').status_code == 422
        assert client.get('/api/digest/export').headers['content-type'].startswith('text/markdown')
        assert 'DTSTART;VALUE=DATE:20270102' in client.get('/api/calendar.ics').text
        assert client.delete(path, headers=headers).status_code == 200
        assert client.get('/api/tracker').json() == []

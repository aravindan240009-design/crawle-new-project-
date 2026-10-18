import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

import pytest

from backend.db import Database
from backend.fixtures import fixture_collect
from backend.models import Filters, Settings
from backend.query import query_results, csv_export
from backend.scanner import acquire, execute_run, Busy, recover, stage_item
from backend.scheduler import next_time


async def scan(db, collector=fixture_collect):
    run = acquire(db)
    await execute_run(db, run, collector=collector)
    return run


async def test_atomic_versions_history_and_bookmarks(db):
    first = await scan(db)
    before = query_results(db, Filters())
    assert before['total'] == 2
    item = before['items'][0]
    db.execute('INSERT INTO item_state VALUES (?,1,0,?)', (item['id'], 'Keep my notes'))
    run = acquire(db)
    changed, _ = await fixture_collect(db.sources()[0], None)
    changed[0]['title'] = 'Staged change should not leak'
    stage_item(db, run, db.sources()[0].id, changed[0])
    assert 'Staged change' not in json.dumps(query_results(db, Filters()))
    db.execute('UPDATE scan_runs SET cancel=1 WHERE id=?', (run,))
    await execute_run(db, run, collector=fixture_collect)
    assert query_results(db, Filters())['snapshot'] == first
    second = await scan(db)
    assert second != first
    old = query_results(db, Filters(snapshot=first))
    assert [i['version_id'] for i in old['items']] == [i['version_id'] for i in before['items']]
    restored = Database(db.path)
    assert query_results(restored, Filters(bookmarked=True))['items'][0]['notes'] == 'Keep my notes'


async def test_partial_failure_and_total_failure(db):
    first = await scan(db)
    async def partial(source, fetcher):
        if source.id == 'demo-cloud':
            raise RuntimeError('offline')
        return await fixture_collect(source, fetcher)
    second = await scan(db, partial)
    assert db.rows('SELECT status FROM scan_runs WHERE id=?', (second,))[0]['status'] == 'completed_with_errors'
    items = query_results(db, Filters())['items']
    assert len(items) == 2 and next(i for i in items if i['source_id'] == 'demo-cloud')['stale'] == 1
    async def fail(*args):
        raise RuntimeError('all offline')
    failed = await scan(db, fail)
    assert db.rows('SELECT status FROM scan_runs WHERE id=?', (failed,))[0]['status'] == 'failed'
    assert query_results(db, Filters())['snapshot'] == second


async def test_missing_rediscovery_does_not_withdraw(db):
    await scan(db)
    async def empty(source, fetcher):
        _, page = await fixture_collect(source, fetcher)
        return [], page
    await scan(db, empty)
    items = query_results(db, Filters())['items']
    assert len(items) == 2 and all(i['stale'] for i in items)
    assert all(i['lifecycle'] != 'withdrawn' for i in items)


async def test_alerts_are_idempotent(db):
    await scan(db)
    count = len(db.rows('SELECT * FROM alerts'))
    assert count == 2
    await scan(db)
    assert len(db.rows('SELECT * FROM alerts')) == count


def test_cross_process_lock_and_recovery(db):
    first = acquire(db)
    script = 'from backend.db import Database; from backend.scanner import acquire,Busy; import sys;\ntry: acquire(Database(sys.argv[1])); sys.exit(9)\nexcept Busy: sys.exit(0)'
    process = subprocess.run([sys.executable, '-c', script, str(db.path)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    db.execute('UPDATE scan_runs SET heartbeat=? WHERE id=?', (time.time() - 200, first))
    recover(db)
    assert db.rows('SELECT status FROM scan_runs WHERE id=?', (first,))[0]['status'] == 'interrupted'
    assert acquire(db) != first


async def test_cancel_during_collection(db):
    first = await scan(db)
    async def slow(source, fetcher):
        await asyncio.sleep(20)
        return await fixture_collect(source, fetcher)
    run = acquire(db)
    task = asyncio.create_task(execute_run(db, run, collector=slow))
    await asyncio.sleep(.05)
    db.execute('UPDATE scan_runs SET cancel=1 WHERE id=?', (run,))
    await asyncio.wait_for(task, 4)
    assert db.rows('SELECT status FROM scan_runs WHERE id=?', (run,))[0]['status'] == 'canceled'
    assert query_results(db, Filters())['snapshot'] == first


async def test_filters_export_parity(db):
    await scan(db)
    assert query_results(db, Filters(geography='Not eligible'))['total'] == 1
    assert query_results(db, Filters(card='no'))['total'] == 2
    assert query_results(db, Filters(deadline_days=7))['total'] == 0
    assert query_results(db, Filters(min_discount=10))['total'] == 0
    f = Filters(q='opportunity', category='AI', page_size=1)
    assert query_results(db, f)['items'] == query_results(db, f, export=True)['items']
    assert "'=HYPERLINK" in csv_export([{'title': '=HYPERLINK("bad")'}])


def test_schedule_timezone_and_coalescing():
    settings = Settings(armed=True, mode='daily')
    assert next_time(settings, datetime(2026, 10, 9, 1, tzinfo=timezone.utc)) == '2026-10-09T02:30:00+00:00'
    assert next_time(settings, datetime(2026, 10, 9, 5, tzinfo=timezone.utc)) == '2026-10-10T02:30:00+00:00'
    assert next_time(Settings()) is None
    continuous = Settings(armed=True, mode='continuous', continuous_minutes=60)
    assert next_time(continuous, datetime(2026, 10, 9, 1, tzinfo=timezone.utc)) == '2026-10-09T02:00:00+00:00'

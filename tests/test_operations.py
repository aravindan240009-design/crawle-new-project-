import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from backend.db import Database
from backend.fixtures import fixture_collect
from backend.models import Settings, now
from backend.scanner import acquire, execute_run
from backend.scheduler import loop
from backend.summary import summarize


async def test_scheduler_coalesces_missed_runs(db, monkeypatch):
    calls = []
    async def fake_run(database, run):
        calls.append(run)
        database.execute("UPDATE scan_runs SET status='completed' WHERE id=?", (run,))
    monkeypatch.setattr('backend.scheduler.execute_run', fake_run)
    db.execute('UPDATE settings SET value=? WHERE id=1', (Settings(armed=True, discovery_enabled=False).model_dump_json(),))
    db.execute('UPDATE schedule SET next_run=? WHERE id=1', ((datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),))
    tasks = set()
    worker = asyncio.create_task(loop(db, tasks))
    await asyncio.sleep(.1)
    worker.cancel()
    await asyncio.gather(worker, *tasks, return_exceptions=True)
    assert len(calls) == 1
    assert db.rows('SELECT next_run FROM schedule')[0]['next_run'] > now()
    second_worker = asyncio.create_task(loop(db, set()))
    await asyncio.sleep(.1)
    second_worker.cancel()
    await asyncio.gather(second_worker, return_exceptions=True)
    assert len(calls) == 1


async def test_backup_restore_and_real_process_restart(db, tmp_path):
    run = acquire(db)
    await execute_run(db, run, collector=fixture_collect)
    oid = db.rows('SELECT opportunity_id FROM membership LIMIT 1')[0]['opportunity_id']
    db.execute('INSERT INTO item_state VALUES (?,1,0,?)', (oid, 'Persist across a process restart'))
    backup = tmp_path / 'backup.sqlite'
    db.backup(backup)
    target = tmp_path / 'restored'
    env = dict(os.environ, RADAR_DATA_DIR=str(tmp_path / 'cli-state'))
    result = subprocess.run([sys.executable, '-m', 'backend', 'restore', str(backup), '--into', str(target)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    check = subprocess.run([sys.executable, '-c', 'from backend.db import Database; import sys; d=Database(sys.argv[1]); print(d.rows("SELECT notes FROM item_state")[0]["notes"]); print(d.settings().armed)', str(target / 'radar.sqlite')], capture_output=True, text=True)
    assert check.returncode == 0
    assert 'Persist across a process restart' in check.stdout and 'False' in check.stdout


async def test_model_unavailable_falls_back(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError('Local model unavailable')
    monkeypatch.setattr(httpx.AsyncClient, 'post', unavailable)
    summary, state = await summarize({'summary': 'Confirmed benefit\nRestrictions unknown\nDeadline not stated'}, Settings(model_enabled=True, model_name='fixture-model'))
    assert summary.startswith('Confirmed benefit')
    assert 'template used' in state


async def test_no_due_sources_is_skipped(db):
    for source in db.sources():
        db.execute('UPDATE sources SET health=? WHERE id=?', (json.dumps({'last_attempt': now()}), source.id))
    run = acquire(db, 'incremental')
    await execute_run(db, run)
    assert db.rows('SELECT status FROM scan_runs WHERE id=?', (run,))[0]['status'] == 'skipped'
    assert not db.rows('SELECT * FROM alerts')

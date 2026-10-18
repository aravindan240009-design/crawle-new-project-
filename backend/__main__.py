import argparse
import asyncio
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
import yaml

from .db import Database
from .models import Source
from .scanner import acquire, execute_run, Busy


def main():
    parser = argparse.ArgumentParser(description='Local Global Opportunity Radar')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('serve')
    scan = sub.add_parser('scan')
    scan.add_argument('--source', action='append', default=[])
    scan.add_argument('--incremental', action='store_true')
    discovery = sub.add_parser('discover', help='Run a bounded dynamic discovery campaign')
    discovery.add_argument('--pages', type=int, default=30)
    discovery.add_argument('--queries', type=int, default=8)
    discovery.add_argument('--seconds', type=int, default=300)
    sub.add_parser('backup').add_argument('path', type=Path)
    restore = sub.add_parser('restore')
    restore.add_argument('path', type=Path)
    restore.add_argument('--into', type=Path, required=True, help='New data directory; never overwrites an existing database')
    sub.add_parser('delete-local-data').add_argument('--confirm', choices=['DELETE-LOCAL-DATA'], required=True)
    sub.add_parser('export-sources').add_argument('path', type=Path)
    sub.add_parser('import-sources').add_argument('path', type=Path)
    args = parser.parse_args()
    if args.command == 'serve':
        uvicorn.run('backend.api:app', host='127.0.0.1', port=int(os.environ.get('RADAR_PORT', '8765')), access_log=False)
        return
    db = Database()
    db.initialize()
    if args.command == 'scan':
        try:
            run = acquire(db, 'incremental' if args.incremental else 'full', args.source)
        except Busy as exc:
            print(str(exc))
            raise SystemExit(3)
        asyncio.run(execute_run(db, run))
        row = db.rows('SELECT id,status,metrics,error FROM scan_runs WHERE id=?', (run,))[0]
        row['metrics'] = json.loads(row['metrics'])
        row['sources'] = [{**r, 'diagnostics': json.loads(r['diagnostics'])} for r in db.rows('SELECT source_id,status,diagnostics FROM source_runs WHERE run_id=?', (run,))]
        print(json.dumps(row, indent=2))
        raise SystemExit(0 if row['status'] == 'completed' else 2 if row['status'] == 'completed_with_errors' else 1)
    if args.command == 'discover':
        from .discovery import run_campaign
        from .discovery_store import CampaignConfig, create_campaign
        config = CampaignConfig(page_budget=args.pages, query_budget=args.queries, seconds=args.seconds)
        cid = create_campaign(db, config)
        asyncio.run(run_campaign(db, cid))
        print(json.dumps(db.rows('SELECT id,status,metrics,error FROM campaigns WHERE id=?', (cid,))[0]))
    if args.command == 'backup':
        if args.path.exists():
            parser.error('Backup target already exists; choose a new filename')
        db.backup(args.path)
        print(f'Consistent SQLite backup saved to {args.path}')
    if args.command == 'restore':
        target = args.into.resolve() / 'radar.sqlite'
        if not args.path.is_file() or target.exists():
            parser.error('Backup must exist and destination radar.sqlite must not exist')
        with sqlite3.connect(args.path.resolve().as_uri() + '?mode=ro', uri=True) as source:
            if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                parser.error('Backup integrity check failed')
            target.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(target) as out:
                source.backup(out)
                # Restoring must never silently enable scheduled collection.
                value = json.loads(out.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
                value['armed'] = False
                out.execute('UPDATE settings SET value=? WHERE id=1', (json.dumps(value),))
                out.execute('UPDATE schedule SET next_run=NULL,worker_heartbeat=NULL')
                out.execute("UPDATE scan_runs SET status='interrupted' WHERE status='running'")
                if out.execute("SELECT 1 FROM sqlite_master WHERE name='campaigns'").fetchone():
                    out.execute("UPDATE campaigns SET status='interrupted',heartbeat=0 WHERE status IN ('running','paused')")
                    out.execute("UPDATE frontier SET status='queued',owner=NULL,lease_until=0 WHERE status='fetching'")
                out.commit()
        print(f'Restored to {target}; schedules disarmed. Set RADAR_DATA_DIR to {target.parent} before starting.')
    if args.command == 'delete-local-data':
        heartbeat = db.rows('SELECT worker_heartbeat FROM schedule WHERE id=1')[0]['worker_heartbeat']
        if db.rows("SELECT 1 FROM scan_runs WHERE status='running' UNION ALL SELECT 1 FROM campaigns WHERE status IN ('running','paused')") or (heartbeat and datetime.fromisoformat(heartbeat) > datetime.now(timezone.utc) - timedelta(seconds=40)):
            parser.error('Stop all Radar processes and wait 40 seconds before deleting local data')
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM identity_observations')
            c.execute('UPDATE publication SET snapshot_id=NULL')
            for table in ['pending_alerts', 'alert_deliveries', 'alert_rules', 'live_versions', 'live_membership', 'media_jobs', 'provenance_edges', 'search_hits', 'queries', 'frontier', 'entities', 'repository_observations', 'discovery_events', 'campaigns', 'evidence', 'candidates', 'membership', 'snapshots', 'item_tracking', 'item_state', 'alerts', 'versions', 'opportunities', 'source_runs', 'scan_runs', 'fetch_cache', 'saved_views', 'leads']:
                c.execute('DELETE FROM ' + table)
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='version_search'").fetchone():
                c.execute('DELETE FROM version_search')
            c.execute("UPDATE sources SET health='{}'")
        print('Deleted local results, evidence, history, notes, bookmarks, alerts, views, leads and cache. Source configuration retained.')
    if args.command == 'export-sources':
        args.path.write_text(yaml.safe_dump({'sources': [s.model_dump() for s in db.sources()]}, sort_keys=False), encoding='utf-8')
    if args.command == 'import-sources':
        sources = [Source.model_validate(s) for s in yaml.safe_load(args.path.read_text(encoding='utf-8'))['sources']]
        with db.connect() as c:
            for source in sources:
                c.execute('INSERT INTO sources(id,config) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config', (source.id, source.model_dump_json()))
        print(f'Imported {len(sources)} source configurations; not fetched or validated by import')


if __name__ == '__main__':
    main()

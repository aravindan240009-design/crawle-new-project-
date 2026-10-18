from __future__ import annotations

import json
import os
import sqlite3
import math
from contextlib import contextmanager
from pathlib import Path

import yaml

from .models import Settings, Source

ROOT = Path(__file__).resolve().parent.parent


class Database:
    def __init__(self, path=None):
        self.path = Path(path or Path(os.environ.get('RADAR_DATA_DIR', ROOT / 'data')) / ('demo.sqlite' if os.environ.get('RADAR_FIXTURES') == '1' else 'radar.sqlite'))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        def distance(lat, lon, target_lat, target_lon):
            if lat is None or lon is None:
                return None
            try:
                a, b, x, y = map(math.radians, (float(lat), float(lon), target_lat, target_lon))
                return 6371 * 2 * math.asin(min(1, math.sqrt(math.sin((x-a)/2)**2 + math.cos(a)*math.cos(x)*math.sin((y-b)/2)**2)))
            except (ValueError, TypeError):
                return None
        conn.create_function('distance_km', 4, distance, deterministic=True)
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=15000')
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            version = c.execute('PRAGMA user_version').fetchone()[0]
            if version < 1:
                c.executescript((ROOT / 'backend/migrations/001.sql').read_text())
                c.execute('PRAGMA user_version=1')
            if version < 2:
                c.executescript((ROOT / 'backend/migrations/002.sql').read_text())
                c.execute('PRAGMA user_version=2')
            if version < 3:
                c.executescript((ROOT / 'backend/migrations/003.sql').read_text())
                c.execute('PRAGMA user_version=3')
            if version < 4:
                c.executescript((ROOT / 'backend/migrations/004.sql').read_text())
                c.execute('PRAGMA user_version=4')
            if version < 5:
                c.executescript((ROOT / 'backend/migrations/005.sql').read_text())
                c.execute('PRAGMA user_version=5')
            c.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (Settings().model_dump_json(),))
            c.execute('INSERT OR IGNORE INTO publication VALUES (1,NULL)')
            c.execute('INSERT OR IGNORE INTO schedule VALUES (1,NULL,NULL)')
            if os.environ.get('RADAR_FIXTURES') == '1':
                from .fixtures import demo_sources
                seed = demo_sources()
            else:
                seed = [Source.model_validate(raw) for raw in yaml.safe_load((ROOT / 'sources/registry.yaml').read_text(encoding='utf-8'))['sources']]
            for source in seed:
                c.execute('INSERT OR IGNORE INTO sources(id,config) VALUES (?,?)', (source.id, source.model_dump_json()))
            try:
                c.execute('CREATE VIRTUAL TABLE IF NOT EXISTS version_search USING fts5(version_id UNINDEXED,title,summary,provider)')
            except sqlite3.OperationalError:
                pass  # Results use a parameterized LIKE fallback on SQLite without FTS5.

    def rows(self, sql, args=()):
        with self.connect() as c:
            return [dict(row) for row in c.execute(sql, args)]

    def execute(self, sql, args=()):
        with self.connect() as c:
            return c.execute(sql, args).rowcount

    def settings(self):
        return Settings.model_validate_json(self.rows('SELECT value FROM settings WHERE id=1')[0]['value'])

    def sources(self):
        return [Source.model_validate_json(r['config']) for r in self.rows('SELECT config FROM sources ORDER BY id')]

    def backup(self, path):
        with self.connect() as c, sqlite3.connect(path) as out:
            c.backup(out)


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

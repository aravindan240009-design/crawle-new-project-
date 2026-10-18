"""Deterministic local query benchmark; isolated database, never real results."""
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path

from backend.db import Database, dump
from backend.models import Filters, now
from backend.query import query_results


def main():
    with tempfile.TemporaryDirectory(prefix='radar-benchmark-') as directory:
        db = Database(Path(directory) / 'benchmark.sqlite')
        db.initialize()
        timestamp = now()
        with db.connect() as c:
            c.execute('INSERT INTO scan_runs(id,status,started,heartbeat,mode,roster) VALUES (?,?,?,?,?,?)', ('bench', 'completed', timestamp, 0, 'fixture benchmark', '[]'))
            c.execute('INSERT INTO snapshots VALUES (?,?)', ('bench', timestamp))
            c.execute('UPDATE publication SET snapshot_id=?', ('bench',))
            for i in range(10000):
                identity = str(i)
                data = dict(id=identity, title=f'Benchmark cloud program {i}', summary='Fixture only', provider='Benchmark', category='Cloud', kind='credits', geography='Unclear', confidence=65, lifecycle='uncertain')
                c.execute('INSERT INTO opportunities VALUES (?,?,?)', (identity, f'https://example.com/benchmark/{i}', timestamp))
                c.execute('INSERT INTO versions VALUES (?,?,?,?,?)', (identity, identity, identity, dump(data), timestamp))
                c.execute('INSERT INTO membership VALUES (?,?,?,?,?)', ('bench', identity, identity, timestamp, 0))
                c.execute('INSERT INTO version_search VALUES (?,?,?,?)', (identity, data['title'], data['summary'], data['provider']))
        times = []
        for _ in range(30):
            t = time.perf_counter()
            result = query_results(db, Filters(q='cloud', category='Cloud', page_size=24))
            times.append((time.perf_counter() - t) * 1000)
        print(json.dumps({'timestamp': timestamp, 'platform': platform.platform(), 'python': platform.python_version(), 'processor': platform.processor(), 'rows': 10000, 'iterations': len(times), 'result_total': result['total'], 'query_p50_ms': round(statistics.median(times), 2), 'query_p95_ms': round(sorted(times)[28], 2)}, indent=2))


if __name__ == '__main__':
    main()

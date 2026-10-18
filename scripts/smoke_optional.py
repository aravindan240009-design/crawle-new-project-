"""Explicit low-volume validation of the disabled public community/search leads."""
import asyncio
import json

from backend.db import Database
from backend.extract import collect
from backend.fetch import Fetcher


async def main():
    db = Database()
    db.initialize()
    fetcher = Fetcher(db, concurrency=1)
    results = []
    try:
        for source in db.sources():
            if source.id not in ('hn-community', 'hn-search'):
                continue
            try:
                items, page = await collect(source, fetcher)
                results.append({'source': source.id, 'status': page.status, 'candidates': len(items), 'retrieved': page.retrieved, 'url': page.url})
            except Exception as exc:
                results.append({'source': source.id, 'status': getattr(exc, 'status', 'failure'), 'error': str(exc)})
    finally:
        await fetcher.close()
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    asyncio.run(main())

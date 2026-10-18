"""Dynamic discovery: search -> frontier -> permitted fetch -> live evidence."""
import asyncio
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import timedelta
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .db import dump
from .discovery_search import github_search, plan_queries, record_hit, repository_fields, run_query, search_local
from .discovery_store import (CampaignConfig, claim_task, commit_live, emit, ensure_worker,
                             finish_campaign, finish_task, queue_url)
from .extract import build_item, canonical_url, official, text_html
from .fetch import Fetcher, Page, FetchError
from .models import Source, now

RELEVANT = re.compile(r'offer|discount|sale|coupon|free|credit|scholar|grant|fellowship|internship|career|event|hackathon|workshop|pricing|benefit|terms|apply|release|github|சலுகை|தள்ளுபடி|இலவச|வேலை', re.I)


def source_for(db, url, category):
    for source in db.sources():
        if official(url, source.official_domains):
            return source.model_copy(update={'category': category, 'url': url})
    host = urlsplit(url).hostname
    return Source(id='discovered-' + hashlib.sha256(host.encode()).hexdigest()[:12], name=host,
                  adapter='html', url=url, family='discovered', category=category, provider=host,
                  official_domains=[], notes='Automatically discovered; issuer identity unassessed')


def provisional(db, url, title, snippet, category, provenance):
    source = source_for(db, url, category)
    # Even a result on a known domain is not page evidence.
    source = source.model_copy(update={'official_domains': []})
    page = Page(url, snippet, 'text/plain', 0, '', now())
    item = build_item(source, page, title=title or urlsplit(url).hostname, text=snippet)
    item.update(publication_state='provisional', confidence=10, verification='Unverified',
                summary='Provisional discovery — source has not been fetched. ' + (snippet[:500] or 'No search excerpt provided.'),
                evidence=[], provenance=provenance, issuer_status='unassessed', media_status='not_checked')
    return item


def extract_page(db, task, page):
    from .discovery_identity import observe_identity, issuer_support, apply_issuer_support
    source = source_for(db, page.url, task['category'])
    title, text, _ = text_html(page.body)
    if re.search(r'^(?:just a moment|access denied|attention required|verify you are human|log ?in|sign in)(?:\b|[.!])', title, re.I) or ('captcha' in page.body.lower() and len(text) < 500):
        raise FetchError('Access challenge or login wall; no bypass attempted', 'blocked')
    item = build_item(source, page)
    for field, pattern in [('booking_window', r'(?:book|booking)\s+(?:from\s+)?(\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+(\d{4}-\d{2}-\d{2})'),
                           ('travel_window', r'(?:travel|stay)\s+(?:from\s+)?(\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+(\d{4}-\d{2}-\d{2})')]:
        match = re.search(pattern, text, re.I)
        item[field] = None
        if match:
            from datetime import date
            try:
                start, end = date.fromisoformat(match[1]), date.fromisoformat(match[2])
                if start <= end:
                    item[field] = {'start': match[1], 'end': match[2], 'precision': 'source date only; cutoff/timezone unknown', 'issuer_confirmed': bool(source.official_domains)}
                    item['evidence'].append(dict(field=field, url=page.url, excerpt=match[0], retrieved=page.retrieved, content_hash=page.content_hash))
            except ValueError:
                pass
    for field, label in [('travel_origin', 'origin'), ('travel_destination', 'destination')]:
        match = re.search(r'\b' + label + r'\s*:\s*([^\n]{1,80})', text, re.I)
        item[field] = match[1].strip() if match else None
    item.update(publication_state='evidence_reviewed', issuer_status='registered official domain' if source.official_domains else 'unassessed', media_status='none_detected')
    if not source.official_domains:
        # Retain observed text with its provenance, without granting issuer trust.
        claim = item.get('benefit') or text[:280]
        if claim:
            item['evidence'].append(dict(field='page_observation', url=page.url, excerpt=claim[:280], retrieved=page.retrieved, content_hash=page.content_hash))
        item['confidence_reasons'] = ['Public page fetched; issuer identity and redemption remain unconfirmed']
        observe_identity(db, page)
        apply_issuer_support(item, issuer_support(db, page), page, text)
    soup = BeautifulSoup(page.body, 'html.parser')
    # Exact structured coordinates are observations, never inferred from a city name.
    for node in soup.select('script[type="application/ld+json"]')[:10]:
        try:
            data = json.loads(node.string or node.get_text())
            records = data if isinstance(data, list) else [data]
            for record in records:
                if not isinstance(record, dict):
                    continue
                geo = record.get('geo') or (record.get('location') or {}).get('geo') if isinstance(record.get('location', {}), dict) else record.get('geo')
                if isinstance(geo, dict):
                    lat, lon = float(geo['latitude']), float(geo['longitude'])
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        item.update(latitude=lat, longitude=lon, coordinate_basis='Source-declared structured coordinates; not independently geocoded')
                        item['evidence'].append(dict(field='coordinates', url=page.url, excerpt=f'Structured coordinates: {lat}, {lon}', retrieved=page.retrieved, content_hash=page.content_hash))
                        break
        except (ValueError, TypeError, KeyError):
            pass
    media = []
    for node in soup.select('video[src],audio[src],video source[src],audio source[src],track[src]')[:8]:
        media.append({'url': urljoin(page.url, node['src']), 'kind': 'captions' if node.name == 'track' else 'media', 'language': node.get('srclang', 'unknown')})
    # Images are evidence candidates only when their description relates to an offer.
    for node in soup.select('img[src]')[:40]:
        if RELEVANT.search(node.get('alt', '')):
            media.append({'url': urljoin(page.url, node['src']), 'kind': 'image', 'language': 'unknown'})
    if media:
        item['media_status'] = 'media_pending'
    links = []
    identities = db.rows('SELECT links FROM identity_observations WHERE url=?', (canonical_url(page.url).rstrip('/'),))
    if identities:
        links.extend((url, 'identity_cross_reference') for url in json.loads(identities[0]['links'])[:5])
    links.extend((urljoin(page.url, a['href']), 'author_profile') for a in soup.select('a[rel~="author"][href]')[:3])
    if task['depth'] < 5:
        for a in soup.select('a[href],link[href]'):
            href, label = a.get('href', ''), a.get_text(' ', strip=True)
            relation = 'feed' if 'alternate' in a.get('rel', []) and any(x in a.get('type', '') for x in ('rss', 'atom')) else 'link'
            if relation == 'feed' or RELEVANT.search(href + ' ' + label):
                links.append((urljoin(page.url, href), relation))
        if 'xml' in page.content_type:
            try:
                root = ET.fromstring(page.body)
                for node in root.iter():
                    if node.tag.rsplit('}', 1)[-1] in ('link', 'loc'):
                        value = node.get('href') or (node.text or '').strip()
                        if value:
                            links.append((urljoin(page.url, value), 'feed_entry'))
                        if len(links) >= 40:
                            break
            except ET.ParseError:
                pass
    media.sort(key=lambda m: {'captions': 0, 'image': 1, 'media': 2}[m['kind']])
    return item, links[:30], media[:8]


async def run_campaign(db, cid, fetcher=None, search=search_local, use_crawlee=True):
    row = db.rows('SELECT * FROM campaigns WHERE id=?', (cid,))[0]
    generation = row['generation']
    config = CampaignConfig.model_validate_json(row['config'])
    if fetcher is None and os.environ.get('RADAR_FIXTURES') == '1':
        from .fixtures import DiscoveryFixtureWeb, discovery_fixture_search
        fetcher, search = DiscoveryFixtureWeb(), discovery_fixture_search
        config = config.model_copy(update={'github': False})
        emit(db, cid, 'fixture_mode', metadata={'fixture': True, 'note': 'Offline test data; no live source coverage'})
    fetcher = fetcher or Fetcher(db, db.settings().concurrency)
    started = time.monotonic()
    metrics, domains, category_counts = Counter(json.loads(row['metrics'])), Counter(), Counter()
    metrics['queries_attempted'] = len(db.rows("SELECT id FROM discovery_events WHERE campaign_id=? AND stage IN ('query_completed','query_failed')", (cid,)))
    metrics['pages_attempted'] = len(db.rows("SELECT id FROM discovery_events WHERE campaign_id=? AND stage='task_leased'", (cid,)))
    pages_reserved = len(db.rows("SELECT DISTINCT task_id FROM discovery_events WHERE campaign_id=? AND stage IN ('task_completed','task_failed')", (cid,)))
    owner = f'{cid}:{generation}'
    budget_scope = None
    remaining = config.seconds

    async def heartbeat():
        while True:
            def beat():
                with db.connect() as c:
                    count = c.execute("UPDATE campaigns SET heartbeat=?,metrics=? WHERE id=? AND generation=? AND status IN ('running','paused')", (time.time(), dump(dict(metrics)), cid, generation)).rowcount
                    if count:
                        c.execute('UPDATE frontier SET lease_until=? WHERE owner=?', (time.time()+90, owner))
            await asyncio.to_thread(beat)
            await asyncio.sleep(2)

    async def gate():
        nonlocal remaining
        while True:
            state = await asyncio.to_thread(db.rows, 'SELECT status,generation FROM campaigns WHERE id=?', (cid,))
            if not state or state[0]['generation'] != generation or state[0]['status'] not in ('running', 'paused'):
                raise asyncio.CancelledError()
            if state[0]['status'] == 'running':
                if budget_scope and budget_scope.when() is None:
                    budget_scope.reschedule(asyncio.get_running_loop().time()+remaining)
                return
            if budget_scope and budget_scope.when() is not None:
                remaining = max(.01, budget_scope.when()-asyncio.get_running_loop().time())
                budget_scope.reschedule(None)
            await asyncio.sleep(.2)

    async def add(url, parent, category, title='', snippet='', depth=0, novel=True, relation='link', region='', language='en'):
        try:
            await gate()
            if metrics['urls_queued'] >= config.queued_url_budget:
                return None
            fid, inserted = await asyncio.to_thread(queue_url, db, cid, url, parent, category, region, language, depth, novel, relation)
            if inserted:
                metrics['urls_queued'] += 1
                item = await asyncio.to_thread(provisional, db, url, title, snippet, category, [{'url': url, 'parent': parent, 'relation': relation}])
                await asyncio.to_thread(commit_live, db, cid, generation, item)
            return fid
        except Exception as exc:
            emit(db, cid, 'url_rejected', str(url)[:2048], code=str(exc)[:200])
            return None

    async def process(task):
        timer = time.perf_counter()
        try:
            await gate()
            emit(db, cid, 'fetch_started', task['url'], task=task['id'])
            repo_path = urlsplit(task['url']).path.strip('/').split('/')
            is_repo = urlsplit(task['url']).hostname == 'github.com' and len(repo_path) == 2 and task['category'] == 'Open source'
            page = await fetcher.get('https://api.github.com/repos/' + '/'.join(repo_path) if is_repo else task['url'])
            metrics['bytes_received'] += len(page.body.encode())
            emit(db, cid, 'fetch_completed', page.url, {'status': page.status, 'cached': page.cached, 'bytes': len(page.body.encode())}, task['id'], duration=time.perf_counter()-timer)
            if config.browser and metrics['browser_attempted'] < config.browser_budget and 'html' in page.content_type and len(text_html(page.body)[1]) < 120:
                from .discovery_browser import render
                metrics['browser_attempted'] += 1
                try:
                    page = await render(fetcher, page, lambda stage, **kw: emit(db, cid, stage, task['url'], task=task['id'], **kw))
                except Exception as exc:
                    emit(db, cid, 'browser_unavailable', task['url'], code=str(exc)[:300])
            if is_repo:
                repo = json.loads(page.body)
                item = provisional(db, task['url'], repo['full_name'], repo.get('description') or '', 'Open source', [{'url': page.url, 'relation': 'repository_api'}])
                item.update(repository_fields(db, repo))
                item.update(publication_state='evidence_reviewed', media_status='none_detected', summary=(repo.get('description') or 'Repository metadata collected.')[:500] + '\n' + item['license_note'])
                item['evidence'] = [dict(field='repository_metadata', url=page.url, excerpt=f"{repo['full_name']}: {item['stars']} stars; license declaration {item['license_spdx'] or 'unknown'}", retrieved=page.retrieved, content_hash=page.content_hash)]
                try:
                    release_page = await fetcher.get('https://api.github.com/repos/' + '/'.join(repo_path) + '/releases?per_page=1')
                    metrics['bytes_received'] += len(release_page.body.encode())
                    releases = json.loads(release_page.body)
                    if isinstance(releases, list) and releases:
                        release = releases[0]
                        item['latest_release'] = {k: release.get(k) for k in ('id', 'tag_name', 'name', 'published_at', 'html_url', 'prerelease')}
                        item['evidence'].append(dict(field='latest_release', url=release_page.url, excerpt=str(release.get('name') or release.get('tag_name'))[:200], retrieved=release_page.retrieved, content_hash=release_page.content_hash))
                    emit(db, cid, 'repository_releases_checked', release_page.url, {'releases': len(releases) if isinstance(releases, list) else 0}, task['id'])
                except Exception as exc:
                    item['release_status'] = 'unavailable'
                    emit(db, cid, 'repository_releases_unavailable', task['url'], code=str(exc)[:200])
                links, media = [], []
            else:
                item, links, media = await asyncio.to_thread(extract_page, db, task, page)
                origin = urlsplit(page.url)
                robots = getattr(fetcher, 'robots', {}).get(f'{origin.scheme}://{origin.netloc}')
                if robots and task['depth'] == 0:
                    links.extend((url, 'sitemap') for url in (robots.site_maps() or [])[:3])
                # Redirects keep the discovered identity, and record final evidence URL.
                item['discovery_url'] = task['url']
                if item.get('official_url'):
                    item['official_url'] = task['url']
            emit(db, cid, 'evidence_extracted', page.url, {'fields': [e['field'] for e in item['evidence']], 'verification': item['verification']}, task['id'])
            # Pause stops commits as well as dispatch. Cancel never removes old results.
            await gate()
            await asyncio.to_thread(commit_live, db, cid, generation, item)
            metrics['pages_completed'] += 1
            if task['depth'] < config.max_depth:
                for url, relation in links:
                    await add(url, page.url, task['category'], depth=task['depth']+1, relation=relation)
            for media_item in media:
                from .discovery_media import register_media
                await asyncio.to_thread(register_media, db, cid, task['id'], media_item)
            await asyncio.to_thread(finish_task, db, cid, generation, task, config, None, len(page.body.encode()))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            metrics['pages_failed'] += 1
            await asyncio.to_thread(finish_task, db, cid, generation, task, config, str(exc)[:300])

    beat = asyncio.create_task(heartbeat())
    try:
        async with asyncio.timeout(config.seconds) as budget_scope:
            queries = await asyncio.to_thread(plan_queries, db, config.categories, max(0, config.query_budget-metrics['queries_attempted']))
            for query in queries:
                await gate()
                hits, status = await run_query(db, cid, query, search)
                metrics['queries_attempted'] += 1
                metrics['queries_completed' if status == 'completed' else 'queries_failed'] += 1
                for rank, hit in enumerate(hits, 1):
                    fid = await add(hit['url'], 'query:' + query['id'], query['category'], hit.get('title', ''), hit.get('snippet', ''), relation='search_hit', region=query['region'], language=query['language'])
                    if fid:
                        record_hit(db, cid, query, hit, rank)
                if status == 'unavailable':
                    # One failed fixed sidecar attempt is sufficient for this cycle.
                    break
            if config.github and 'Open source' in config.categories:
                await gate()
                emit(db, cid, 'repository_search_started', 'https://api.github.com/search/repositories')
                try:
                    repos = await github_search(fetcher)
                    emit(db, cid, 'repository_search_completed', metadata={'hits': len(repos)})
                    for repo in repos:
                        url = repo['html_url']
                        await add(url, 'github_repository_search', 'Open source', repo['full_name'], repo.get('description') or '', relation='repository_search')
                        item = provisional(db, url, repo['full_name'], repo.get('description') or '', 'Open source', [{'url': repo['url'], 'relation': 'repository_api'}])
                        item.update(repository_fields(db, repo))
                        item.update(publication_state='evidence_reviewed', summary=(repo.get('description') or 'Repository metadata collected.')[:500] + '\n' + item['license_note'], media_status='none_detected')
                        item['evidence'] = [dict(field='repository_metadata', url=repo['url'], excerpt=f"{repo['full_name']}: {item['stars']} stars; license declaration {item['license_spdx'] or 'unknown'}", retrieved=now(), content_hash=hashlib.sha256(dump(repo).encode()).hexdigest())]
                        await gate()
                        commit_live(db, cid, generation, item)
                        metrics['repositories_observed'] += 1
                except Exception as exc:
                    emit(db, cid, 'repository_search_failed', code=str(exc)[:300])
            if config.seeds:
                for source in db.sources():
                    if source.enabled and source.category in config.categories and source.adapter == 'html':
                        await add(source.url, 'seed:' + source.id, source.category, source.name, depth=0, novel=False, relation='seed')
            # SQLite is the authoritative frontier. Crawlee dispatches one bounded
            # batch at a time using our connection-pinned, robots-aware transport.
            while pages_reserved < config.page_budget:
                await gate()
                import psutil
                memory = psutil.virtual_memory()
                disk_bytes = db.path.stat().st_size + sum(p.stat().st_size for p in db.path.parent.glob(db.path.name + '-*'))
                metrics['system_memory_percent'] = memory.percent
                metrics['database_bytes'] = disk_bytes
                if disk_bytes >= config.disk_limit_mb*1024*1024 or metrics['bytes_received'] >= config.byte_budget_mb*1_000_000 or (memory.percent > 99.5 and os.environ.get('RADAR_FIXTURES') != '1'):
                    emit(db, cid, 'resource_backpressure', metadata={'database_bytes': disk_bytes, 'memory_percent': memory.percent, 'bytes_received': metrics['bytes_received']})
                    break
                concurrency = 1 if memory.percent > 90 else db.settings().concurrency
                if memory.percent > 90 and not metrics['memory_throttled']:
                    metrics['memory_throttled'] = 1
                    config = config.model_copy(update={'browser': False, 'media_budget': 0})
                    emit(db, cid, 'resource_throttled', metadata={'concurrency': 1, 'memory_percent': memory.percent, 'browser_and_media': 'deferred'})
                batch = []
                for _ in range(min(concurrency, config.page_budget-pages_reserved)):
                    want_novel = metrics['novel_attempted'] < max(1, (metrics['pages_attempted']+1)*config.exploration_share)
                    task = await asyncio.to_thread(claim_task, db, cid, generation, config, want_novel, domains, category_counts)
                    if not task:
                        break
                    batch.append(task)
                    domains[task['domain']] += 1
                    category_counts[task['category']] += 1
                    metrics['category_attempts:' + task['category']] += 1
                    metrics['pages_attempted'] += 1
                    pages_reserved += 1
                    metrics['novel_attempted'] += task['novel']
                if not batch:
                    break
                if use_crawlee:
                    from crawlee import ConcurrencySettings
                    from crawlee.crawlers import BasicCrawler
                    from crawlee.storage_clients import MemoryStorageClient
                    tasks_by_url = {t['url']: t for t in batch}
                    async def handler(context):
                        await process(tasks_by_url[context.request.url])
                    crawler = BasicCrawler(request_handler=handler, storage_client=MemoryStorageClient(),
                        max_request_retries=0, max_session_rotations=0, use_session_pool=False,
                        retry_on_blocked=False, max_requests_per_crawl=len(batch), configure_logging=False,
                        request_handler_timeout=timedelta(seconds=config.seconds),
                        concurrency_settings=ConcurrencySettings(min_concurrency=1, desired_concurrency=len(batch), max_concurrency=len(batch)))
                    await crawler.run([t['url'] for t in batch])
                else:
                    await asyncio.gather(*(process(t) for t in batch))
            await gate()
            from .discovery_media import process_media
            await process_media(db, cid, fetcher, limit=config.media_budget, gate=gate, generation=generation)
            await gate()
            metrics['total_seconds'] = round(time.monotonic()-started, 3)
            finish_campaign(db, cid, generation, dict(metrics))
    except TimeoutError:
        metrics['total_seconds'] = round(time.monotonic()-started, 3)
        emit(db, cid, 'budget_exhausted', metadata={'seconds': config.seconds})
        try:
            finish_campaign(db, cid, generation, dict(metrics), 'Time budget exhausted; committed discoveries retained')
        except asyncio.CancelledError:
            pass
    except asyncio.CancelledError:
        # Controlled pause/cancel/recovery changes are already durable. Shutdown
        # leaves an interrupted campaign that can resume its remaining frontier.
        db.execute("UPDATE campaigns SET status='interrupted',error='Worker stopped; resume available' WHERE id=? AND generation=? AND status IN ('running','paused')", (cid, generation))
    except Exception as exc:
        emit(db, cid, 'worker_failed', code=str(exc)[:300])
        try:
            finish_campaign(db, cid, generation, dict(metrics), str(exc)[:300])
        except asyncio.CancelledError:
            pass
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
        db.execute("UPDATE frontier SET status='queued',owner=NULL,lease_until=0 WHERE owner=?", (owner,))
        await fetcher.close()

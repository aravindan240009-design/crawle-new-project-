"""Bounded query planning and the single explicitly allowed local search sidecar."""
import hashlib
import json
from urllib.parse import urlencode

import httpx

from .db import dump
from .discovery_store import CATEGORIES, emit
from .models import now

SEARX_URL = 'http://127.0.0.1:8088/search'
TERMS = {
    'Food': 'restaurant cafe discount opening offer', 'Travel': 'travel hotel transport discount',
    'Local services': 'salon gym clinic opening discount', 'Shopping': 'sale coupon student discount',
    'Events': 'free event hackathon competition registration', 'Learning': 'scholarship free course workshop',
    'Jobs': 'internship fellowship job application', 'AI': 'AI tool free credits release',
    'Cloud': 'cloud startup credits free tier', 'Developer': 'developer tools free program',
    'Open source': 'open source repository release developer tools', 'Opportunities': 'grant competition application',
}
REGIONS = ['Chennai', 'India', 'worldwide', 'Bengaluru', 'Singapore', 'Europe', 'Africa', 'Americas']
TAMIL = {'Food': 'உணவகம் தள்ளுபடி', 'Travel': 'பயணம் சலுகை', 'Local services': 'புதிய கடை திறப்பு சலுகை',
         'Shopping': 'தள்ளுபடி சலுகைகள்', 'Events': 'இலவச நிகழ்ச்சி', 'Learning': 'கல்வி உதவித்தொகை',
         'Jobs': 'வேலைவாய்ப்பு', 'AI': 'செயற்கை நுண்ணறிவு இலவச', 'Cloud': 'கிளவுட் இலவச',
         'Developer': 'மென்பொருள் இலவச', 'Open source': 'திறந்த மூல மென்பொருள்', 'Opportunities': 'போட்டி உதவித்தொகை'}


def plan_queries(db, categories, budget):
    # Persist a finite rotating bank; least-recently-attempted balances coverage.
    with db.connect() as c:
        for category in categories:
            for region in REGIONS:
                for language in (['en', 'ta', 'transliterated'] if region == 'Chennai' else ['en']):
                    query = (TAMIL[category] + ' சென்னை' if language == 'ta' else
                             TERMS[category] + ' Chennai salugai thallupadi' if language == 'transliterated' else TERMS[category] + ' ' + region)
                    signature = hashlib.sha256(query.encode()).hexdigest()
                    c.execute('INSERT OR IGNORE INTO queries(id,signature,query,category,region,language,engine) VALUES (?,?,?,?,?,?,?)',
                              (signature[:24], signature, query, category, region, language, 'searxng'))
        rows = c.execute("SELECT * FROM queries ORDER BY coalesce(last_attempt,''),CASE region WHEN 'Chennai' THEN 0 WHEN 'India' THEN 1 WHEN 'worldwide' THEN 2 ELSE 3 END,CASE language WHEN 'en' THEN 0 WHEN 'ta' THEN 1 ELSE 2 END,id").fetchall()
    selected = []
    # First cover categories; then fill the remaining budget, rotating language/region.
    for row in rows:
        if row['category'] in categories and row['category'] not in [r['category'] for r in selected]:
            selected.append(dict(row))
            if len(selected) >= budget:
                return selected[:budget]
    selected_ids = {r['id'] for r in selected}
    selected.extend(dict(r) for r in rows if r['category'] in categories and r['id'] not in selected_ids)
    return selected[:budget]


class SearchHits(list):
    def __init__(self, rows, failures):
        super().__init__(rows)
        self.failures = failures


async def search_local(query, limit=8):
    # Fixed literal address only. Never honor environment proxies or redirects.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=20) as client:
        async with client.stream('GET', SEARX_URL, params={'q': query, 'format': 'json'}) as response:
            response.raise_for_status()
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 2_000_000:
                    raise ValueError('SearXNG response exceeds budget')
    value = json.loads(chunks)
    failures = value.get('unresponsive_engines', [])
    if failures and not value.get('results'):
        raise RuntimeError('No search results; upstream engine failures: ' + '; '.join(str(x)[:120] for x in failures)[:600])
    return SearchHits([{'url': r['url'], 'title': str(r.get('title', ''))[:240], 'snippet': str(r.get('content', ''))[:800],
             'engine': ','.join(r.get('engines', [r.get('engine', 'unknown')]))[:120]}
            for r in value.get('results', [])[:limit] if isinstance(r, dict) and isinstance(r.get('url'), str)], failures)


async def run_query(db, cid, query, search=search_local):
    import time
    started = time.perf_counter()
    db.execute("UPDATE queries SET status='running',last_attempt=? WHERE id=?", (now(), query['id']))
    emit(db, cid, 'query_dispatched', query['query'], {'engine': 'searxng', 'category': query['category'], 'language': query['language'], 'region': query['region']}, query['id'])
    try:
        hits = await search(query['query'])
        diagnostics = {'hits': len(hits), 'unresponsive_engines': getattr(hits, 'failures', [])}
        status = 'completed'
        emit(db, cid, 'query_completed', query['query'], diagnostics, query['id'], code='partial_engine_failure' if diagnostics['unresponsive_engines'] else None, duration=time.perf_counter()-started)
    except Exception as exc:
        hits, status = [], 'unavailable'
        diagnostics = {'reason': str(exc)[:300], 'endpoint': SEARX_URL}
        emit(db, cid, 'query_failed', query['query'], diagnostics, query['id'], code='search_unavailable', duration=time.perf_counter()-started)
    db.execute('UPDATE queries SET last_attempt=?,status=?,diagnostics=? WHERE id=?', (now(), status, dump(diagnostics), query['id']))
    return hits, status


def record_hit(db, cid, query, hit, rank):
    hid = hashlib.sha256((cid+query['id']+hit['url']).encode()).hexdigest()[:32]
    db.execute('INSERT OR IGNORE INTO search_hits VALUES (?,?,?,?,?,?,?,?)',
               (hid, cid, query['id'], hit.get('engine', 'searxng'), rank, hit['url'], hit.get('snippet', '')[:800], now()))
    return hid


async def github_search(fetcher, query='topic:developer-tools archived:false'):
    url = 'https://api.github.com/search/repositories?' + urlencode({'q': query, 'sort': 'updated', 'per_page': 6})
    page = await fetcher.get(url)
    return json.loads(page.body).get('items', [])


# This is an explicit classification subset, not a substitute for legal review.
OPEN_LICENSES = {'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', 'MPL-2.0', 'GPL-2.0', 'GPL-3.0', 'LGPL-2.1', 'LGPL-3.0', 'AGPL-3.0', 'Unlicense', 'CC0-1.0'}


def repository_fields(db, repo, observed=None):
    from datetime import datetime, timedelta
    observed = observed or now()
    rid = str(repo['id'])
    baseline_cutoff = (datetime.fromisoformat(observed)-timedelta(hours=1)).isoformat()
    prior = db.rows('SELECT * FROM repository_observations WHERE repo_id=? AND observed<=? ORDER BY observed DESC LIMIT 1', (rid, baseline_cutoff))
    stars, forks = int(repo.get('stargazers_count', 0)), int(repo.get('forks_count', 0))
    license_id = (repo.get('license') or {}).get('spdx_id')
    classification = 'open-source license declared' if license_id in OPEN_LICENSES else 'unknown / no recognized license'
    if license_id in ('BUSL-1.1', 'SSPL-1.0'):
        classification = 'source available / restricted'
    fields = {'repository': repo.get('full_name'), 'stars': stars, 'forks': forks,
              'license_spdx': license_id, 'license_class': classification,
              'license_note': 'Repository API declaration; review LICENSE and dependency terms before use.',
              'repository_updated': repo.get('updated_at'), 'archived': bool(repo.get('archived')),
              'language': repo.get('language'), 'topics': repo.get('topics', []), 'star_velocity_per_day': None,
              'observation_time': observed, 'trend_basis': 'One observation; velocity unavailable'}
    if prior:
        seconds = (datetime.fromisoformat(observed)-datetime.fromisoformat(prior[0]['observed'])).total_seconds()
        # Avoid noisy second-apart requests being presented as a meaningful trend.
        if seconds >= 3600:
            fields['star_velocity_per_day'] = (stars-prior[0]['stars']) * 86400 / seconds
            fields['trend_basis'] = f"Measured since {prior[0]['observed']} ({seconds/3600:.1f} hours)"
    db.execute('INSERT OR IGNORE INTO repository_observations VALUES (?,?,?,?,?)', (rid, observed, stars, forks, dump(fields)))
    return fields

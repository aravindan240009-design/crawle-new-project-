import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.discovery import provisional, run_campaign
from backend.discovery import extract_page
from backend.discovery_identity import observe_identity
from backend.discovery_alerts import Rule, deliver_pending, delivery_time, save_rule
from backend.discovery_search import repository_fields
from backend.discovery_store import (CampaignConfig, campaign_control, claim_task, commit_live,
    create_campaign, events, finish_campaign, queue_url, recover_campaigns)
from backend.fetch import Page, Fetcher, FetchError
from backend.models import Filters, Settings, now
from backend.query import query_results
from backend.scanner import Busy, acquire


class FixtureWeb:
    def __init__(self, delay=0):
        self.delay = delay
        self.started = asyncio.Event()
        self.calls = []
    async def get(self, url, **kwargs):
        self.started.set()
        self.calls.append(url)
        await asyncio.sleep(self.delay)
        body = '<title>Chennai launch offer</title><main>Opening discount 25% off. Venue: Chennai.<a href="https://second.example/free-offer">Free workshop</a></main>'
        return Page(url, body, 'text/html', 200, 'fixture-hash', now())
    async def close(self):
        pass


async def fixture_search(query):
    return [{'url': 'https://unknown.example/offer', 'title': 'New shop offer', 'snippet': 'Opening discount advertised', 'engine': 'fixture'}]


def config(**kw):
    return CampaignConfig(**{'seeds': False, 'github': False, 'query_budget': 1, 'page_budget': 2, 'categories': ['Food'], **kw})


async def test_unknown_domain_provisional_then_evidence_and_recursive_discovery(db):
    cid = create_campaign(db, config())
    web = FixtureWeb(.15)
    worker = asyncio.create_task(run_campaign(db, cid, web, fixture_search, use_crawlee=False))
    await asyncio.wait_for(web.started.wait(), 3)
    items = query_results(db, Filters())['items']
    assert len(items) == 1 and items[0]['publication_state'] == 'provisional'
    assert items[0]['verification'] == 'Unverified'
    assert not db.rows('SELECT * FROM snapshots')
    first_id = items[0]['id']
    db.execute('INSERT INTO item_state VALUES (?,1,0,?)', (first_id, 'Preserve across versions'))
    cursor = events(db)[-1]['id']
    await worker
    assert 'https://unknown.example/offer' in web.calls
    assert 'https://second.example/free-offer' in web.calls
    result = query_results(db, Filters(q='Chennai'))
    assert result['total'] == 2
    assert all(i['publication_state'] == 'evidence_reviewed' for i in result['items'])
    assert query_results(db, Filters(bookmarked=True))['items'][0]['notes'] == 'Preserve across versions'
    assert db.rows('SELECT status FROM campaigns')[0]['status'] == 'completed'
    replay = events(db, cursor)
    assert all(e['id'] > cursor for e in replay)
    assert any(e['stage'] == 'offer_updated' for e in replay)
    assert all(r['issuer_status'] == 'unassessed' for r in db.rows('SELECT * FROM entities'))
    assert db.rows("SELECT * FROM frontier WHERE domain='unknown.example'")[0]['status'] == 'visited'


async def test_cancel_keeps_live_result_no_late_commit(db):
    cid = create_campaign(db, config())
    web = FixtureWeb(.3)
    worker = asyncio.create_task(run_campaign(db, cid, web, fixture_search, use_crawlee=False))
    await asyncio.wait_for(web.started.wait(), 3)
    before = query_results(db, Filters())['items'][0]
    campaign_control(db, cid, 'cancel')
    await worker
    after = query_results(db, Filters())['items'][0]
    assert before['version_id'] == after['version_id']
    assert db.rows('SELECT status FROM campaigns')[0]['status'] == 'canceled'
    assert not db.rows('SELECT * FROM snapshots')


async def test_pause_resume_same_worker(db):
    cid = create_campaign(db, config(page_budget=1))
    web = FixtureWeb(.1)
    worker = asyncio.create_task(run_campaign(db, cid, web, fixture_search, use_crawlee=False))
    await web.started.wait()
    campaign_control(db, cid, 'pause')
    await asyncio.sleep(.25)
    assert query_results(db, Filters())['items'][0]['publication_state'] == 'provisional'
    assert not campaign_control(db, cid, 'resume')
    await worker
    assert query_results(db, Filters(publication_state='evidence_reviewed'))['total'] == 1


def test_recovery_generation_fences_old_worker_and_archive_immutable(db):
    cid = create_campaign(db, config())
    item = provisional(db, 'https://new.example/offer', 'First', 'Discount', 'Food', [])
    commit_live(db, cid, 1, item)
    db.execute('UPDATE campaigns SET heartbeat=0 WHERE id=?', (cid,))
    recover_campaigns(db)
    assert campaign_control(db, cid, 'resume')
    with pytest.raises(asyncio.CancelledError):
        commit_live(db, cid, 1, item)
    finish_campaign(db, cid, 2, {})
    archived = query_results(db, Filters(snapshot=cid))['items'][0]
    next_id = create_campaign(db, config())
    item.update(title='Updated', publication_state='evidence_reviewed')
    commit_live(db, next_id, 1, item)
    assert query_results(db, Filters())['items'][0]['title'] == 'Updated'
    assert query_results(db, Filters(snapshot=cid))['items'][0]['version_id'] == archived['version_id']
    assert query_results(db, Filters(snapshot=cid))['items'][0]['title'] == 'First'


def test_cross_mode_lock_and_frontier_leases(db):
    cid = create_campaign(db, config())
    with pytest.raises(Busy):
        acquire(db)
    with pytest.raises(Busy):
        create_campaign(db)
    queue_url(db, cid, 'https://new.example/offer', 'query:test', 'Food')
    first = claim_task(db, cid, 1, config(), True, {})
    assert first
    assert claim_task(db, cid, 1, config(), True, {}) is None
    campaign_control(db, cid, 'cancel')
    run = acquire(db)
    with pytest.raises(Busy):
        create_campaign(db)
    assert run


async def test_actual_crawlee_dispatch_uses_only_supplied_transport(db):
    cid = create_campaign(db, config(page_budget=1))
    web = FixtureWeb()
    await run_campaign(db, cid, web, fixture_search)
    assert db.rows('SELECT status,error FROM campaigns')[0] == {'status': 'completed', 'error': None}
    assert web.calls == ['https://unknown.example/offer']
    assert query_results(db, Filters(publication_state='evidence_reviewed'))['total'] == 1


def test_repo_license_and_observed_velocity(db):
    repo = {'id': 123, 'full_name': 'owner/repo', 'stargazers_count': 100, 'forks_count': 10, 'license': None}
    a = repository_fields(db, repo, '2026-10-01T00:00:00+00:00')
    assert a['star_velocity_per_day'] is None
    assert a['license_class'] == 'unknown / no recognized license'
    repo.update(stargazers_count=124, license={'spdx_id': 'MIT'})
    b = repository_fields(db, repo, '2026-10-02T00:00:00+00:00')
    assert b['star_velocity_per_day'] == 24
    assert b['license_class'] == 'open-source license declared'
    repo['license'] = {'spdx_id': 'NOASSERTION'}
    assert repository_fields(db, repo)['license_class'] == 'unknown / no recognized license'


def test_rule_provisional_optin_cooldown_quiet_hours_and_api_detail(db):
    db.execute('UPDATE settings SET value=? WHERE id=1', (Settings(quiet_start='00:00', quiet_end='00:00').model_dump_json(),))
    save_rule(db, 'reviewed', Rule(name='Reviewed', min_confidence=0))
    save_rule(db, 'early', Rule(name='Early', provisional=True, min_confidence=0))
    cid = create_campaign(db, config())
    item = provisional(db, 'https://new.example/deal', 'A deal', 'Claim', 'Food', [])
    oid = commit_live(db, cid, 1, item)
    assert len(db.rows('SELECT * FROM pending_alerts')) == 1
    deliver_pending(db)
    assert len(db.rows('SELECT * FROM alerts')) == 1
    commit_live(db, cid, 1, item)
    assert not db.rows('SELECT * FROM pending_alerts')
    settings = Settings(quiet_start='22:00', quiet_end='08:00')
    assert delivery_time(settings, datetime(2026, 10, 9, 18, tzinfo=timezone.utc)) == '2026-10-10T02:30:00+00:00'
    with TestClient(create_app(db)) as client:
        detail = client.get('/api/opportunities/' + oid)
        assert detail.status_code == 200 and len(detail.json()['history']) == 1
        assert client.get('/api/results?publication_state=provisional').json()['total'] == 1
        assert client.get('/api/export/json?publication_state=provisional').json()['total'] == 1
        assert client.get('/api/discovery/events?after=0').json()
        assert client.post('/api/discovery/campaigns', json={}).status_code == 403


@pytest.mark.parametrize('url', ['http://127.0.0.1/test', 'http://[::1]/', 'https://new.example/a?token=secret', 'https://new.example/a?X-Amz-Signature=secret'])
def test_frontier_rejects_private_and_signed(db, url):
    cid = create_campaign(db, config())
    with pytest.raises((ValueError, FetchError)):
        queue_url(db, cid, url, '', 'Food')


async def test_direct_media_redirect_uses_public_target_gate(db, monkeypatch):
    fetcher = Fetcher(db)
    calls = []
    async def allowed(*args):
        return 0
    async def request(url, *args):
        calls.append(url)
        return 302, {'location': 'http://169.254.169.254/latest'}, b''
    monkeypatch.setattr(fetcher, '_allowed', allowed)
    monkeypatch.setattr(fetcher, '_request', request)
    with pytest.raises(FetchError):
        await fetcher.blob('https://public.example/video.mp4')
    assert len(calls) == 1
    await fetcher.close()


def test_small_shop_identity_needs_reciprocal_links_contact_and_location(db):
    profile, directory = 'https://social.example/shops/cafe', 'https://directory.example/chennai/cafe'
    def identity_page(url, target, phone='4412345678'):
        data = {'@type': 'LocalBusiness', 'name': 'Example Cafe', 'address': {'addressLocality': 'Chennai'}, 'telephone': phone, 'sameAs': [target]}
        return Page(url, '<script type="application/ld+json">' + json.dumps(data) + '</script>', 'text/html', 200, 'fixture', now())
    observe_identity(db, identity_page(profile, directory))
    post = Page('https://social.example/posts/123', '<title>Cafe offer</title><a rel="author" href="/shops/cafe">Example Cafe</a><main>Opening discount 25% off. Location: Coimbatore branch.</main>', 'text/html', 200, 'post', now())
    task = {'category': 'Food', 'depth': 0}
    item, _, _ = extract_page(db, task, post)
    assert item['verification'] == 'Unverified'
    observe_identity(db, identity_page(directory, profile, phone='4499999999'))
    assert extract_page(db, task, post)[0]['verification'] == 'Unverified'
    observe_identity(db, identity_page(directory, profile))
    item = extract_page(db, task, post)[0]
    assert item['verification'] == 'Issuer-posted; redemption not independently confirmed'
    assert item['location'] != 'Chennai'  # Identity locality is not a branch offer location.
    assert item['geography'] == 'Unclear'
    assert any('old post' in r for r in item['risk_flags'])
    assert len([e for e in item['evidence'] if e['field'] == 'issuer_identity']) == 2


def test_coordinate_filter_excludes_unknowns_and_exports_match(db):
    cid = create_campaign(db, config())
    item = provisional(db, 'https://public.example/near', 'Near offer', 'Discount', 'Food', [])
    item.update(latitude=13.08, longitude=80.27)
    commit_live(db, cid, 1, item)
    unknown = provisional(db, 'https://public.example/unknown', 'Unknown point', 'Discount', 'Food', [])
    commit_live(db, cid, 1, unknown)
    nearby = query_results(db, Filters(near_me=True))
    assert nearby['total'] == 1 and nearby['items'][0]['title'] == 'Near offer'
    assert query_results(db, Filters(near_me=True), export=True)['items'] == nearby['items']


def test_access_challenge_is_not_empty_success(db):
    page = Page('https://social.example/post', '<title>Log in to Instagram</title><main>Enter your password</main>', 'text/html', 200, 'login', now())
    with pytest.raises(FetchError, match='Access challenge'):
        extract_page(db, {'category': 'Food', 'depth': 0}, page)


async def test_interrupted_single_page_budget_retries_unfinished_task(db):
    cid = create_campaign(db, config(page_budget=1))
    web = FixtureWeb(10)
    worker = asyncio.create_task(run_campaign(db, cid, web, fixture_search, use_crawlee=False))
    await asyncio.wait_for(web.started.wait(), 3)
    worker.cancel()
    await worker
    assert db.rows('SELECT status FROM campaigns')[0]['status'] == 'interrupted'
    assert campaign_control(db, cid, 'resume')
    resumed = FixtureWeb()
    await run_campaign(db, cid, resumed, fixture_search, use_crawlee=False)
    assert resumed.calls == ['https://unknown.example/offer']
    assert query_results(db, Filters(publication_state='evidence_reviewed'))['total'] == 1


def test_explicit_travel_windows_keep_date_precision_and_untrusted_evidence(db):
    page = Page('https://travel.example/offer', '<title>Travel coupon</title><main>Coupon INR 500 discount.\nBook from 2026-10-10 to 2026-10-20\nTravel from 2026-11-01 to 2026-12-01\nOrigin: Chennai\nDestination: Singapore</main>', 'text/html', 200, 'fixture', now())
    item = extract_page(db, {'category': 'Travel', 'depth': 0}, page)[0]
    assert item['currency'] == 'INR' and item['amount'] is None
    assert item['booking_window']['issuer_confirmed'] is False
    assert item['travel_window']['start'] == '2026-11-01'
    assert 'timezone unknown' in item['booking_window']['precision']
    assert item['deadline'] is None
    assert any(e['field'] == 'booking_window' for e in item['evidence'])


def test_category_dispatch_fairness(db):
    cfg = config(categories=['Food', 'Travel', 'Shopping'])
    cid = create_campaign(db, cfg)
    for category in cfg.categories:
        for i in range(3):
            queue_url(db, cid, f'https://{category.lower()}{i}.example/offer', 'fixture', category)
    counts, selected = {}, []
    for _ in range(3):
        task = claim_task(db, cid, 1, cfg, True, {}, counts)
        selected.append(task['category'])
        counts[task['category']] = counts.get(task['category'], 0)+1
    assert set(selected) == set(cfg.categories)


async def test_caption_job_commits_timestamped_evidence_and_digest_change(db):
    from backend.discovery_media import register_media, process_media
    from backend.planning import weekly_digest
    cid = create_campaign(db, config(query_budget=0))
    url = 'https://public.example/offer'
    fid, _ = queue_url(db, cid, url, 'fixture', 'Food')
    item = provisional(db, url, 'Caption offer', 'Discount claim', 'Food', [])
    item.update(publication_state='evidence_reviewed', media_status='media_pending')
    commit_live(db, cid, 1, item)
    register_media(db, cid, fid, {'url': 'https://public.example/captions.vtt', 'kind': 'captions', 'language': 'en'})
    class MediaFixture:
        async def blob(self, url):
            return url, 'text/vtt', b'WEBVTT\n00:00:01.000 --> 00:00:03.000\n25% off, new customers only'
    await process_media(db, cid, MediaFixture())
    assert db.rows('SELECT status FROM media_jobs')[0]['status'] == 'extracted'
    current = query_results(db, Filters())['items'][0]
    assert current['media_status'] == 'extracted'
    assert current['verification'] == 'Unverified'
    detail = json.loads(db.rows('SELECT v.data FROM live_membership m JOIN versions v ON v.id=m.version_id')[0]['data'])
    assert any(e['field'] == 'machine_captions' and '00:00:01' in e['excerpt'] for e in detail['evidence'])
    assert weekly_digest(db)['changes']


def test_repo_growth_uses_older_baseline_despite_frequent_observations(db):
    repo = {'id': 5, 'full_name': 'owner/frequent', 'stargazers_count': 10, 'forks_count': 1}
    repository_fields(db, repo, '2026-10-01T00:00:00+00:00')
    repository_fields(db, repo, '2026-10-01T00:45:00+00:00')
    repo['stargazers_count'] = 12
    measured = repository_fields(db, repo, '2026-10-01T01:00:00+00:00')
    assert measured['star_velocity_per_day'] == 48


async def test_repository_revisit_collects_release_metadata_without_running_code(db):
    cfg = config(query_budget=0, page_budget=1, categories=['Open source'])
    cid = create_campaign(db, cfg)
    queue_url(db, cid, 'https://github.com/owner/tool', 'fixture', 'Open source')
    class RepoWeb(FixtureWeb):
        async def get(self, url, **kwargs):
            self.calls.append(url)
            data = [{'id': 1, 'name': 'v1.0', 'tag_name': 'v1.0', 'published_at': '2026-10-01T00:00:00Z', 'html_url': 'https://github.com/owner/tool/releases/tag/v1.0', 'prerelease': False}] if '/releases?' in url else {'id': 7, 'full_name': 'owner/tool', 'description': 'A public tool', 'license': {'spdx_id': 'MIT'}, 'stargazers_count': 5, 'forks_count': 1}
            return Page(url, json.dumps(data), 'application/json', 200, 'fixture', now())
    web = RepoWeb()
    await run_campaign(db, cid, web, fixture_search, use_crawlee=False)
    item = query_results(db, Filters())['items'][0]
    assert item['latest_release']['tag_name'] == 'v1.0'
    assert item['license_class'] == 'open-source license declared'
    assert len(web.calls) == 2


def test_deadline_rule_pending_correction_and_cross_process_lock(db):
    import subprocess
    import sys
    save_rule(db, 'dates', Rule(name='Dates', min_confidence=0))
    cid = create_campaign(db, config())
    item = provisional(db, 'https://example.org/deadline', 'Deadline test', 'Claim', 'Food', [])
    item.update(publication_state='evidence_reviewed', deadline=(datetime.now(timezone.utc)+timedelta(days=5)).isoformat(), deadline_precision='instant')
    commit_live(db, cid, 1, item)
    assert db.rows("SELECT * FROM pending_alerts WHERE type='deadline reminder'")
    item.update(verification='Contradicted', lifecycle='withdrawn')
    commit_live(db, cid, 1, item)
    assert not db.rows("SELECT * FROM pending_alerts WHERE type='deadline reminder'")
    assert db.rows("SELECT * FROM pending_alerts WHERE type='correction'")
    code = "from backend.db import Database; from backend.discovery_store import create_campaign; import sys; create_campaign(Database(sys.argv[1]))"
    process = subprocess.run([sys.executable, '-c', code, str(db.path)], capture_output=True, text=True, timeout=10)
    assert process.returncode != 0 and 'already active' in process.stderr

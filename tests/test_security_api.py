import asyncio
import ipaddress
import json
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.fetch import FetchError, Fetcher, PublicBackend, validate_url, validate_ip, retry_after
from backend.fixtures import fixture_collect
from backend.scanner import acquire, execute_run


@pytest.mark.parametrize('url', ['http://127.0.0.1/x', 'http://[::1]/', 'http://169.254.169.254/latest', 'http://10.1.2.3', 'file:///etc/passwd', 'https://user:pass@example.com', 'http://example.com:8080'])
def test_private_urls(url):
    with pytest.raises((FetchError, ValueError)):
        validate_url(url)


@pytest.mark.parametrize('value', ['192.168.1.1', '::ffff:127.0.0.1', 'fc00::1', 'fe80::1', '100.64.0.1', '0.0.0.0', '224.0.0.1'])
def test_private_addresses(value):
    with pytest.raises(FetchError):
        validate_ip(value)


async def test_dns_rebinding_is_pinned(monkeypatch):
    backend = PublicBackend()
    loop = asyncio.get_running_loop()
    async def dns(*args, **kwargs):
        return [(2, 1, 6, '', ('93.184.216.34', 443))]
    monkeypatch.setattr(loop, 'getaddrinfo', dns)
    called = []
    async def connect(host, *args):
        called.append(host)
        return object()
    monkeypatch.setattr(backend.backend, 'connect_tcp', connect)
    await backend.connect_tcp('attacker.example', 443)
    assert called == ['93.184.216.34']
    async def private(*args, **kwargs):
        return [(2, 1, 6, '', ('127.0.0.1', 443))]
    monkeypatch.setattr(loop, 'getaddrinfo', private)
    with pytest.raises(FetchError):
        await backend.connect_tcp('attacker.example', 443)


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b'hello'):
        self.status = status
        self.headers = headers or [(b'content-type', b'text/html')]
        self.body = body
    async def aiter_stream(self):
        yield self.body


class FakePool:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    @asynccontextmanager
    async def stream(self, method, url, **kwargs):
        self.calls.append((url, kwargs))
        yield next(self.responses)
    async def aclose(self):
        pass


async def test_cache_304_and_headers(db):
    pool = FakePool([FakeResponse(headers=[(b'content-type', b'text/html'), (b'etag', b'v1')]), FakeResponse(304)])
    fetcher = Fetcher(db, pool=pool)
    first = await fetcher.get('https://example.com', robots=False, interval=0)
    second = await fetcher.get('https://example.com', robots=False, interval=0)
    assert first.body == second.body == 'hello' and second.cached
    assert pool.calls[-1][1]['headers']['If-None-Match'] == 'v1'


async def test_redirect_and_oversized(db):
    pool = FakePool([FakeResponse(302, [(b'location', b'http://127.0.0.1/secret')])])
    with pytest.raises(FetchError):
        await Fetcher(db, pool=pool).get('https://example.com', robots=False, interval=0)
    assert len(pool.calls) == 1
    pool = FakePool([FakeResponse(body=b'x' * 2_000_001)])
    with pytest.raises(FetchError, match='2 MB'):
        await Fetcher(db, pool=pool).get('https://example.com', robots=False, interval=0)


async def test_robots_and_rate_limit(db):
    pool = FakePool([FakeResponse(body=b'User-agent: *\nDisallow: /private')])
    with pytest.raises(FetchError, match='robots'):
        await Fetcher(db, pool=pool).get('https://example.com/private', interval=0)
    pool = FakePool([FakeResponse(429, [(b'retry-after', b'120')])])
    with pytest.raises(FetchError) as error:
        await Fetcher(db, pool=pool).get('https://example.com', robots=False, interval=0)
    assert error.value.status == 'rate_limited'
    assert retry_after('120') == 120


def test_api_security_and_persistence(db):
    app = create_app(db)
    with TestClient(app) as client:
        assert client.get('/api/health').status_code == 200
        assert client.get('/api/session', headers={'Host': 'evil.example'}).status_code == 403
        assert client.get('/api/session', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/scans', json={}).status_code == 403
        token = client.get('/api/session').json()['token']
        headers = {'X-Radar-Token': token}
        assert client.put('/api/settings', json={'concurrency': 999}, headers=headers).status_code == 422
        assert client.post('/api/leads', json={'url': 'http://127.0.0.1/'}, headers=headers).status_code == 422
        assert client.get('/api/results?sort=sql-injection').status_code == 422
        assert client.get('/api/opportunities/no-such-id').status_code == 404
        run = acquire(db)
        asyncio.run(execute_run(db, run, collector=fixture_collect))
        item = client.get('/api/results').json()['items'][0]
        state = {'bookmarked': True, 'dismissed': False, 'notes': '<script>alert(1)</script>'}
        assert client.put('/api/opportunities/' + item['id'] + '/state', json=state, headers=headers).status_code == 200
        response = client.get('/api/results?bookmarked=true')
        assert response.json()['total'] == 1
        assert '<script>' in response.json()['items'][0]['notes']  # React renders text, not HTML.
        exported = client.get('/api/export/json?bookmarked=true').json()
        assert exported['items'] == response.json()['items']
        assert 'frame-ancestors' in response.headers['Content-Security-Policy']

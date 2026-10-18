"""Bounded public-web fetches. DNS is validated at the TCP connection boundary."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import random
import socket
import ssl
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpcore

from .models import now

USER_AGENT = 'OpportunityRadar/0.1 (personal local research; respects robots.txt)'
MAX_BYTES = 2_000_000


class FetchError(Exception):
    def __init__(self, message, status='failure', http_status=None):
        super().__init__(message)
        self.status, self.http_status = status, http_status


def validate_url(url):
    u = urlsplit(url)
    if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password:
        raise FetchError('Only public HTTP(S) URLs without credentials are allowed', 'blocked')
    if u.port not in (None, 80, 443):
        raise FetchError('Only ports 80/443 allowed', 'blocked')
    if u.hostname.lower() in ('localhost', 'metadata.google.internal') or u.hostname.endswith('.local'):
        raise FetchError('Private host rejected', 'blocked')
    try:
        validate_ip(u.hostname)
    except ValueError:
        pass  # DNS names are checked again where connections are established.
    return u


def validate_ip(value):
    ip = ipaddress.ip_address(value.split('%')[0])
    mapped = getattr(ip, 'ipv4_mapped', None)
    if not ip.is_global or (mapped and not mapped.is_global) or ip.is_multicast:
        raise FetchError('Non-public network target rejected', 'blocked')
    return ip


class PublicBackend(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        async with asyncio.timeout(timeout or 20):
            results = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addresses = list(dict.fromkeys(row[4][0] for row in results))
            if not addresses:
                raise FetchError('DNS returned no addresses')
            for address in addresses:
                validate_ip(address)
            # Pass a validated literal IP to the backend: no second hostname lookup.
            # TLS SNI and certificate checks still use the original host in httpcore.
            return await self.backend.connect_tcp(addresses[0], port, timeout, local_address, socket_options)

    async def connect_unix_socket(self, *args, **kwargs):
        raise FetchError('Unix sockets are not permitted', 'blocked')

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


@dataclass
class Page:
    url: str
    body: str
    content_type: str
    status: int
    content_hash: str
    retrieved: str
    cached: bool = False


class Fetcher:
    def __init__(self, db, concurrency=4, pool=None):
        self.db = db
        self.pool = pool or httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(), network_backend=PublicBackend(),
            max_connections=concurrency, max_keepalive_connections=concurrency)
        self.host_locks = defaultdict(asyncio.Lock)
        self.next_host = defaultdict(float)
        self.robots = {}
        self.failures = defaultdict(int)
        self.latencies = []
        self.cache_hits = 0

    async def close(self):
        await self.pool.aclose()

    async def _request(self, url, headers, timeout, interval):
        host = validate_url(url).hostname
        if self.failures[host] >= 3:
            raise FetchError('Host circuit open for this run after repeated failures', 'skipped')
        async with self.host_locks[host]:
            await asyncio.sleep(max(0, self.next_host[host] - time.monotonic()))
            started = time.perf_counter()
            try:
                async with asyncio.timeout(timeout):
                    async with self.pool.stream('GET', url, headers=headers, extensions={
                        'timeout': {'connect': timeout, 'read': timeout, 'write': timeout, 'pool': timeout}
                    }) as response:
                        hs = {k.decode().lower(): v.decode('latin1') for k, v in response.headers}
                        # Request identity encoding, rejecting unsolicited compression before decoding.
                        if hs.get('content-encoding', 'identity').lower() not in ('', 'identity'):
                            raise FetchError('Unexpected compressed response rejected', 'parse_error', response.status)
                        if int(hs.get('content-length', '0')) > MAX_BYTES:
                            raise FetchError('Response exceeds 2 MB budget', 'parse_error', response.status)
                        data = bytearray()
                        async for chunk in response.aiter_stream():
                            data.extend(chunk)
                            if len(data) > MAX_BYTES:
                                raise FetchError('Response exceeds 2 MB budget', 'parse_error', response.status)
                        return response.status, hs, bytes(data)
            except (TimeoutError, httpcore.TimeoutException) as exc:
                self.failures[host] += 1
                raise FetchError('Request timed out', 'timeout') from exc
            finally:
                self.next_host[host] = time.monotonic() + interval
                self.latencies.append(time.perf_counter() - started)

    async def _allowed(self, url, timeout, interval):
        u = validate_url(url)
        origin = f'{u.scheme}://{u.netloc}'
        if origin not in self.robots:
            page = await self.get(origin + '/robots.txt', timeout=timeout, interval=interval, robots=False)
            parser = RobotFileParser()
            parser.parse(page.body.splitlines())
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise FetchError('Disallowed by robots.txt', 'blocked')
        delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*') or 0
        if delay > 120:
            raise FetchError('Robots crawl-delay exceeds scan budget', 'skipped')
        return max(interval, delay)

    async def get(self, url, timeout=20, interval=2, robots=True):
        for redirect in range(6):
            validate_url(url)
            if robots:
                interval = await self._allowed(url, timeout, interval)
            cached = self.db.rows('SELECT * FROM fetch_cache WHERE url=?', (url,))
            old = cached[0] if cached else None
            headers = {'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity', 'Accept': 'text/html, application/json, application/xml, text/plain, */*;q=0.1'}
            if old:
                if old['etag']:
                    headers['If-None-Match'] = old['etag']
                if old['modified']:
                    headers['If-Modified-Since'] = old['modified']
            for attempt in range(3):
                status, hs, data = await self._request(url, headers, timeout, interval)
                if status not in (429, 500, 502, 503, 504):
                    break
                retry = retry_after(hs.get('retry-after'))
                if attempt == 2 or retry > 30:
                    raise FetchError(f'HTTP {status}; retry later', 'rate_limited' if status == 429 else 'failure', status)
                await asyncio.sleep(max(retry, 2 ** attempt + random.random()))
            if status in (301, 302, 303, 307, 308):
                if 'location' not in hs:
                    raise FetchError('Redirect has no location', 'parse_error', status)
                url = urljoin(url, hs['location'])
                continue
            if status == 304 and old:
                self.cache_hits += 1
                self.db.execute('UPDATE fetch_cache SET fetched=? WHERE url=?', (now(), url))
                return Page(url, old['body'], old['content_type'], 304, old['content_hash'], now(), True)
            if not robots and status in (404, 410):
                return Page(url, '', 'text/plain', status, '', now())
            if status >= 400:
                self.failures[validate_url(url).hostname] += 1
                raise FetchError(f'HTTP {status}', 'blocked' if status in (401, 403) else 'failure', status)
            ct = hs.get('content-type', '').split(';')[0].lower()
            if not any(x in ct for x in ('html', 'xml', 'json', 'text/plain', 'javascript', 'text/css', 'text/vtt')):
                raise FetchError(f'Unsupported content type: {ct}', 'parse_error', status)
            body = data.decode('utf-8', errors='replace')
            digest = hashlib.sha256(data).hexdigest()
            self.db.execute('INSERT OR REPLACE INTO fetch_cache VALUES (?,?,?,?,?,?,?)',
                            (url, hs.get('etag'), hs.get('last-modified'), body, ct, digest, now()))
            return Page(url, body, ct, status, digest, now(), bool(old and old['content_hash'] == digest))
        raise FetchError('Too many redirects', 'blocked')

    async def blob(self, url, timeout=20, interval=2):
        """Bounded direct media only, using the same pinned transport and robots gate.

        No manifest, segment or downloader can open its own network connection.
        The normal 2 MB response limit applies before decoding.
        """
        for _ in range(6):
            validate_url(url)
            interval = await self._allowed(url, timeout, interval)
            status, headers, data = await self._request(url, {'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity'}, timeout, interval)
            if status in (301, 302, 303, 307, 308):
                url = urljoin(url, headers.get('location', ''))
                continue
            if status >= 400:
                raise FetchError(f'HTTP {status}', 'blocked' if status in (401, 403) else 'failure', status)
            content_type = headers.get('content-type', '').split(';')[0].lower()
            allowed = ('image/png', 'image/jpeg', 'image/webp', 'audio/mpeg', 'audio/wav', 'audio/x-wav', 'video/mp4', 'text/vtt', 'application/x-subrip')
            if content_type not in allowed:
                raise FetchError(f'Direct media type unsupported: {content_type}; manifests are not downloaded', 'unsupported')
            return url, content_type, data
        raise FetchError('Too many media redirects', 'blocked')


def retry_after(value):
    if not value:
        return 0
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError):
            return 0

"""Explicit demo fixtures; activated only with RADAR_FIXTURES=1 and demo.sqlite."""
import asyncio
import hashlib
import os

from .extract import build_item
from .fetch import Page
from .models import Source, now


def demo_sources():
    return [Source(id='demo-' + name, name='DEMO ' + name.title(), adapter='html',
                   provider='Demo ' + name.title(), url=f'https://example.com/{name}',
                   terms_url=f'https://example.com/{name}', category=cat, official_domains=['example.com'])
            for name, cat in [('cloud', 'Cloud'), ('ai', 'AI'), ('students', 'Learning')]]


async def fixture_collect(source, fetcher):
    await asyncio.sleep(2.5 if os.environ.get('RADAR_FIXTURES') == '1' else .05)
    text = ('Free tier includes 100 requests per day.\nAvailable worldwide.\nNo credit card required.\n'
            'Usage limits apply.\nDemo fixture only; this is not a real offer.')
    if source.id == 'demo-students':
        text = 'Free trial for US-student-only applicants.\nA credit card is required.\nAutomatically renews after 30 days.\nDemo fixture only.'
    page = Page(source.url, text, 'text/plain', 200, hashlib.sha256(text.encode()).hexdigest(), now())
    item = build_item(source, page, title=source.name + ' opportunity', text=text)
    item['demo'] = True
    return [item], page


async def discovery_fixture_search(query):
    await asyncio.sleep(.3)
    return [{'url': 'https://unlisted.example/launch-offer', 'title': 'DEMO new cafe opening',
             'snippet': 'DEMO fixture: opening discount; source not yet checked.', 'engine': 'offline fixture'}]


class DiscoveryFixtureWeb:
    async def get(self, url, **kwargs):
        await asyncio.sleep(2.5)
        body = '<title>DEMO cafe launch offer</title><main>DEMO fixture only. Opening discount 25% off. Venue: Chennai. Conditions not fully stated.</main>'
        return Page(url, body, 'text/html', 200, hashlib.sha256(body.encode()).hexdigest(), now())

    async def close(self):
        pass

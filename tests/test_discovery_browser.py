import pytest

from backend.discovery_browser import render
from backend.discovery_media import local_extract
from backend.fetch import FetchError, Page, validate_url
from backend.models import now


async def test_browser_scripts_run_but_private_subrequests_never_connect():
    from playwright.async_api import async_playwright
    from pathlib import Path
    async with async_playwright() as p:
        if not Path(p.chromium.executable_path).exists():
            pytest.skip('Optional Chromium runtime not installed')
    requested = []
    class GuardedFixture:
        async def get(self, url, **kwargs):
            requested.append(url)
            validate_url(url)
            raise FetchError('Fixture denies all other subresources')
    html = '''<html><body><div id="offer"></div><script>
    document.querySelector('#offer').textContent='Rendered discount';
    fetch('http://127.0.0.1/secret').catch(()=>{});
    fetch('http://169.254.169.254/latest').catch(()=>{});
    </script></body></html>'''
    original = Page('https://public.example/offer', html, 'text/html', 200, 'fixture', now())
    stages = []
    result = await render(GuardedFixture(), original, lambda stage, **kw: stages.append((stage, kw)))
    assert 'Rendered discount' in result.body
    assert any('127.0.0.1' in url for url in requested)
    assert stages[-1][1]['metadata']['blocked_requests'] >= 2


def test_caption_timestamps_and_explicit_missing_ocr():
    text, method, language = local_extract(b'WEBVTT\n00:00:01.000 --> 00:00:03.000\n<b>Offer ends today</b>', 'text/vtt', {})
    assert '00:00:01.000' in text and '<b>' not in text and method == 'captions'
    with pytest.raises(RuntimeError, match='missing test runtime'):
        local_extract(b'image', 'image/png', {'ocr': {'available': False, 'reason': 'missing test runtime'}})
